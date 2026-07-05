param(
  [string]$Date = (Get-Date -Format "yyyyMMdd"),
  [string]$OutFile = "",
  [string]$PoolCode = "ttg,had,hhad,crs,hafu",
  [switch]$Force,
  [switch]$MergeExisting,
  [switch]$RefreshPredictions
)

$ErrorActionPreference = "Stop"

function Get-RootDir {
  Split-Path -Parent $PSScriptRoot
}

function Get-TargetDateText {
  param([string]$CompactDate)
  ([datetime]::ParseExact($CompactDate, "yyyyMMdd", $null)).ToString("yyyy-MM-dd")
}

function Get-ExistingMatchMap {
  param([string]$Path)

  $map = @{}
  if (-not (Test-Path $Path)) {
    return $map
  }

  $existingPayload = Get-Content -Raw -Encoding UTF8 $Path | ConvertFrom-Json
  foreach ($existingMatch in @($existingPayload.matches)) {
    if ($existingMatch.matchId) {
      $map[[string]$existingMatch.matchId] = $existingMatch
    }
  }
  return $map
}

function Get-ExistingPayload {
  param([string]$Path)

  if (-not (Test-Path $Path)) {
    return $null
  }

  try {
    return (Get-Content -Raw -Encoding UTF8 $Path | ConvertFrom-Json)
  }
  catch {
    return $null
  }
}

function Get-StandingsRowLookup {
  param($Payload)

  $lookup = @{}
  if (-not $Payload -or -not ($Payload.PSObject.Properties.Name -contains "standingsSnapshot")) {
    return $lookup
  }

  foreach ($group in @($Payload.standingsSnapshot)) {
    $rank = 0
    foreach ($row in @($group.rows)) {
      $rank += 1
      $team = [string]$row.team
      if (-not $team) { continue }
      try { $row | Add-Member -NotePropertyName rank -NotePropertyValue $rank -Force } catch {}
      try { $row | Add-Member -NotePropertyName group -NotePropertyValue ([string]$group.group) -Force } catch {}
      $lookup[$team] = $row
    }
  }
  return $lookup
}

function Get-StandingsContext {
  param(
    [string]$HomeTeam,
    [string]$AwayTeam,
    $StandingsLookup
  )

  $homeRow = if ($StandingsLookup.ContainsKey($HomeTeam)) { $StandingsLookup[$HomeTeam] } else { $null }
  $awayRow = if ($StandingsLookup.ContainsKey($AwayTeam)) { $StandingsLookup[$AwayTeam] } else { $null }
  if (-not $homeRow -or -not $awayRow) {
    return $null
  }

  $homePlayed = [int]$homeRow.played
  $awayPlayed = [int]$awayRow.played
  $homeRemaining = [math]::Max(0, 3 - $homePlayed)
  $awayRemaining = [math]::Max(0, 3 - $awayPlayed)
  $homePoints = [int]$homeRow.points
  $awayPoints = [int]$awayRow.points
  $homeRank = 9
  $awayRank = 9

  $groupTeams = @($StandingsLookup.Values | Where-Object { $_ -eq $homeRow -or $_ -eq $awayRow })
  if ($homeRow.PSObject.Properties.Name -contains "rank") { $homeRank = [int]$homeRow.rank }
  if ($awayRow.PSObject.Properties.Name -contains "rank") { $awayRank = [int]$awayRow.rank }

  return [pscustomobject]@{
    home = $homeRow
    away = $awayRow
    homePoints = $homePoints
    awayPoints = $awayPoints
    homeRemaining = $homeRemaining
    awayRemaining = $awayRemaining
    homePlayed = $homePlayed
    awayPlayed = $awayPlayed
    homeRank = $homeRank
    awayRank = $awayRank
    finalRound = ($homeRemaining -le 1 -and $awayRemaining -le 1)
    bothSafeOnDraw = ($homeRemaining -le 1 -and $awayRemaining -le 1 -and $homePoints -ge 4 -and $awayPoints -ge 4 -and $homeRank -le 2 -and $awayRank -le 2)
    homeDesperate = ($homeRemaining -le 1 -and $homePoints -le 1)
    awayDesperate = ($awayRemaining -le 1 -and $awayPoints -le 1)
    homeCanProtect = ($homeRemaining -le 1 -and $homeRank -le 2 -and $homePoints -ge 4)
    awayCanProtect = ($awayRemaining -le 1 -and $awayRank -le 2 -and $awayPoints -ge 4)
  }
}

function Get-HhadValue {
  param($Hhad, [string]$PrimaryName, [string]$FallbackName = "")

  if (-not $Hhad) {
    return $null
  }
  if ($PrimaryName -and $Hhad.PSObject.Properties.Name -contains $PrimaryName) {
    return $Hhad.$PrimaryName
  }
  if ($FallbackName -and $Hhad.PSObject.Properties.Name -contains $FallbackName) {
    return $Hhad.$FallbackName
  }
  return $null
}

function Get-TopGoalsPrediction {
  param($Ttg, $Had = $null, $Hhad = $null, $Context = $null)

  $pairs = @(
    [pscustomobject]@{ label = "0"; value = [double]$Ttg.s0 },
    [pscustomobject]@{ label = "1"; value = [double]$Ttg.s1 },
    [pscustomobject]@{ label = "2"; value = [double]$Ttg.s2 },
    [pscustomobject]@{ label = "3"; value = [double]$Ttg.s3 },
    [pscustomobject]@{ label = "4"; value = [double]$Ttg.s4 },
    [pscustomobject]@{ label = "5"; value = [double]$Ttg.s5 },
    [pscustomobject]@{ label = "6"; value = [double]$Ttg.s6 },
    [pscustomobject]@{ label = "7+"; value = [double]$Ttg.s7 }
  ) | Where-Object { $_.value -gt 0 } | Sort-Object value

  if (-not $pairs -or $pairs.Count -eq 0) {
    return [pscustomobject]@{
      totalGoals = "2"
      candidates = @("2", "3", "1")
      confidence = "low"
    }
  }

  $topLabel = [string]$pairs[0].label
  $topOdd = [double]$pairs[0].value
  $gap = if ($pairs.Count -gt 1) { [math]::Round([double]$pairs[1].value - [double]$pairs[0].value, 2) } else { 0.0 }

  $homeProb = 0.45
  $drawProb = 0.27
  $awayProb = 0.28
  if ($Had -and $Had.h -and $Had.d -and $Had.a) {
    $rawHome = 1 / [double]$Had.h
    $rawDraw = 1 / [double]$Had.d
    $rawAway = 1 / [double]$Had.a
    $sum = $rawHome + $rawDraw + $rawAway
    if ($sum -gt 0) {
      $homeProb = $rawHome / $sum
      $drawProb = $rawDraw / $sum
      $awayProb = $rawAway / $sum
    }
  }
  else {
    $hhadHome = Get-HhadValue $Hhad "home" "h"
    $hhadDraw = Get-HhadValue $Hhad "draw" "d"
    $hhadAway = Get-HhadValue $Hhad "away" "a"
    if ($hhadHome -and $hhadDraw -and $hhadAway) {
      $rawHome = 1 / [double]$hhadHome
      $rawDraw = 1 / [double]$hhadDraw
      $rawAway = 1 / [double]$hhadAway
      $sum = $rawHome + $rawDraw + $rawAway
      if ($sum -gt 0) {
        $homeProb = $rawHome / $sum
        $drawProb = $rawDraw / $sum
        $awayProb = $rawAway / $sum
      }
    }
  }

  $favoriteProb = [math]::Max($homeProb, $awayProb)
  $favoriteStrong = $favoriteProb -ge 0.56
  $balancedMatch = [math]::Abs($homeProb - $awayProb) -le 0.12
  $drawPressure = $drawProb -ge 0.27
  $hhadHandicap = Get-HhadValue $Hhad "handicap" "fixedOddsGoal"
  if ($hhadHandicap) {
    $handicap = [string]$hhadHandicap
    if ($handicap -match "^-2" -or $handicap -match "^\+2") {
      $favoriteStrong = $true
    }
  }

  if ($topLabel -eq "2" -and $pairs.Count -gt 1 -and [string]$pairs[1].label -eq "3" -and $gap -le 0.28 -and $favoriteStrong) {
    $topLabel = "3"
  }
  elseif ($topLabel -eq "3" -and $pairs.Count -gt 1 -and [string]$pairs[1].label -eq "2" -and $gap -le 0.22 -and ($balancedMatch -or $drawPressure)) {
    $topLabel = "2"
  }
  elseif ($topLabel -eq "1" -and $favoriteStrong -and $topOdd -le 4.9) {
    $topLabel = "2"
  }
  elseif ($topLabel -eq "4" -and $balancedMatch -and $drawPressure) {
    $topLabel = "3"
  }

  if ($Context) {
    if ($Context.bothSafeOnDraw -and $drawPressure) {
      if ($topLabel -eq "4") { $topLabel = "3" }
      elseif ($topLabel -eq "3") { $topLabel = "2" }
      $confidence = if ($favoriteStrong) { "medium" } else { "low" }
    }
    elseif (($Context.homeDesperate -and $awayProb -gt $homeProb) -or ($Context.awayDesperate -and $homeProb -gt $awayProb)) {
      if ($topLabel -eq "1") { $topLabel = "2" }
    }
  }

  $confidence = "medium"
  if ($gap -ge 0.6) {
    $confidence = "high"
  }
  elseif ($gap -lt 0.2) {
    $confidence = "low"
  }
  if ($favoriteStrong -and $confidence -eq "medium" -and ($topLabel -eq "3" -or $topLabel -eq "4")) {
    $confidence = "high"
  }
  if ($balancedMatch -and $drawPressure -and $gap -lt 0.35) {
    $confidence = "low"
  }

  return [pscustomobject]@{
    totalGoals = $topLabel
    candidates = @($pairs | Select-Object -First ([Math]::Min(3, $pairs.Count)) | ForEach-Object { $_.label })
    confidence = $confidence
  }
}

function Get-ResultLean {
  param($Had, $Hhad = $null, $Context = $null)

  $items = @()
  if ($Had -and $Had.h -and $Had.d -and $Had.a) {
    $items = @(
      [pscustomobject]@{ code = "home"; value = [double]$Had.h },
      [pscustomobject]@{ code = "draw"; value = [double]$Had.d },
      [pscustomobject]@{ code = "away"; value = [double]$Had.a }
    )
  }
  else {
    $hhadHome = Get-HhadValue $Hhad "home" "h"
    $hhadDraw = Get-HhadValue $Hhad "draw" "d"
    $hhadAway = Get-HhadValue $Hhad "away" "a"
    if ($hhadHome -and $hhadDraw -and $hhadAway) {
      $items = @(
        [pscustomobject]@{ code = "home"; value = [double]$hhadHome },
        [pscustomobject]@{ code = "draw"; value = [double]$hhadDraw },
        [pscustomobject]@{ code = "away"; value = [double]$hhadAway }
      )
    }
  }
  if (-not $items -or $items.Count -eq 0) {
    return "home"
  }

  $items = $items | Sort-Object value

  $pick = [string]$items[0].code
  if ($Had -and $Had.h -and $Had.d -and $Had.a) {
    $rawHome = 1 / [double]$Had.h
    $rawDraw = 1 / [double]$Had.d
    $rawAway = 1 / [double]$Had.a
  }
  else {
    $rawHome = 1 / [double](Get-HhadValue $Hhad "home" "h")
    $rawDraw = 1 / [double](Get-HhadValue $Hhad "draw" "d")
    $rawAway = 1 / [double](Get-HhadValue $Hhad "away" "a")
  }
  $sum = $rawHome + $rawDraw + $rawAway
  if ($sum -le 0) {
    return $pick
  }

  $homeProb = $rawHome / $sum
  $drawProb = $rawDraw / $sum
  $awayProb = $rawAway / $sum
  if ([math]::Abs($homeProb - $awayProb) -le 0.10 -and $drawProb -ge 0.28) {
    return "draw"
  }

  if ($Context -and $Context.bothSafeOnDraw -and $drawProb -ge 0.27 -and [math]::Abs($homeProb - $awayProb) -le 0.10) {
    return "draw"
  }

  if ($Context -and $Context.finalRound) {
    if ($Context.homeCanProtect -and $Context.awayDesperate -and $pick -eq "home" -and $drawProb -ge 0.24) {
      return "draw"
    }
    if ($Context.awayCanProtect -and $Context.homeDesperate -and $pick -eq "away" -and $drawProb -ge 0.24) {
      return "draw"
    }
  }

  $hhadHandicap = Get-HhadValue $Hhad "handicap" "fixedOddsGoal"
  $hhadHome = Get-HhadValue $Hhad "home" "h"
  $hhadAway = Get-HhadValue $Hhad "away" "a"
  if ($hhadHome -and $hhadAway -and $hhadHandicap) {
    $handicap = [string]$hhadHandicap
    $hHome = [double]$hhadHome
    $hAway = [double]$hhadAway
    if ($handicap -match "^-1" -and $pick -eq "home" -and $hAway -lt $hHome -and $drawProb -ge 0.24) {
      return "home"
    }
    if ($handicap -match "^\+1" -and $pick -eq "away" -and $hHome -lt $hAway -and $drawProb -ge 0.24) {
      return "away"
    }
  }

  return $pick
}

function Convert-ToIntGoals {
  param([string]$Label)
  if ($Label -eq "7+") { return 7 }
  return [int]$Label
}

function Get-ScorePrediction {
  param([string]$GoalLabel, [string]$Lean, $Had = $null, $Hhad = $null, $Context = $null)

  $goals = Convert-ToIntGoals $GoalLabel
  $homeProb = 0.45
  $drawProb = 0.27
  $awayProb = 0.28
  if ($Had -and $Had.h -and $Had.d -and $Had.a) {
    $rawHome = 1 / [double]$Had.h
    $rawDraw = 1 / [double]$Had.d
    $rawAway = 1 / [double]$Had.a
    $sum = $rawHome + $rawDraw + $rawAway
    if ($sum -gt 0) {
      $homeProb = $rawHome / $sum
      $drawProb = $rawDraw / $sum
      $awayProb = $rawAway / $sum
    }
  }
  else {
    $hhadHome = Get-HhadValue $Hhad "home" "h"
    $hhadDraw = Get-HhadValue $Hhad "draw" "d"
    $hhadAway = Get-HhadValue $Hhad "away" "a"
    if ($hhadHome -and $hhadDraw -and $hhadAway) {
      $rawHome = 1 / [double]$hhadHome
      $rawDraw = 1 / [double]$hhadDraw
      $rawAway = 1 / [double]$hhadAway
      $sum = $rawHome + $rawDraw + $rawAway
      if ($sum -gt 0) {
        $homeProb = $rawHome / $sum
        $drawProb = $rawDraw / $sum
        $awayProb = $rawAway / $sum
      }
    }
  }

  $favoriteProb = [math]::Max($homeProb, $awayProb)
  $favoriteStrong = $favoriteProb -ge 0.56
  $balancedMatch = [math]::Abs($homeProb - $awayProb) -le 0.12
  $drawPressure = $drawProb -ge 0.27
  $hhadHandicap = Get-HhadValue $Hhad "handicap" "fixedOddsGoal"
  if ($hhadHandicap) {
    $handicap = [string]$hhadHandicap
    if ($handicap -match "^-2" -or $handicap -match "^\+2") {
      $favoriteStrong = $true
    }
  }

  if ($Context -and $Context.bothSafeOnDraw) {
    if ($Lean -eq "draw") {
      if ($goals -le 2) {
        return [pscustomobject]@{ scores = @("1:1", "0:0"); upset = "1:0" }
      }
      return [pscustomobject]@{ scores = @("1:1", "2:2"); upset = "1:0" }
    }
    if ($Lean -eq "home") {
      if ($goals -le 2) {
        return [pscustomobject]@{ scores = @("1:0", "1:1"); upset = "0:1" }
      }
      return [pscustomobject]@{ scores = @("2:1", "1:1"); upset = "0:1" }
    }
    if ($goals -le 2) {
      return [pscustomobject]@{ scores = @("0:1", "1:1"); upset = "1:0" }
    }
    return [pscustomobject]@{ scores = @("1:2", "1:1"); upset = "2:1" }
  }

  if ($Context -and $Context.finalRound) {
    if ($Context.homeCanProtect -and $Context.awayDesperate -and $Lean -eq "away" -and $goals -le 2) {
      return [pscustomobject]@{ scores = @("1:1", "0:1"); upset = "1:0" }
    }
    if ($Context.awayCanProtect -and $Context.homeDesperate -and $Lean -eq "home" -and $goals -le 2) {
      return [pscustomobject]@{ scores = @("1:1", "1:0"); upset = "0:1" }
    }
  }

  if ($Lean -eq "draw") {
    switch ($goals) {
      0 { return [pscustomobject]@{ scores = @("0:0", "1:1"); upset = "1:0" } }
      1 { return [pscustomobject]@{ scores = @("0:0", "1:1"); upset = "1:0" } }
      2 { return [pscustomobject]@{ scores = @("1:1", "0:0"); upset = "1:0" } }
      3 { return [pscustomobject]@{ scores = @("2:2", "1:1"); upset = "2:1" } }
      default { return [pscustomobject]@{ scores = @("2:2", "1:1"); upset = "3:1" } }
    }
  }

  if ($Lean -eq "away") {
    if ($drawPressure -and $goals -le 2) { return [pscustomobject]@{ scores = @("0:1", "1:1"); upset = "1:0" } }
    switch ($goals) {
      0 { return [pscustomobject]@{ scores = @("0:0", "0:1"); upset = "1:0" } }
      1 { return [pscustomobject]@{ scores = @("0:1", "1:1"); upset = "1:0" } }
      2 { return [pscustomobject]@{ scores = @("0:1", "0:2"); upset = "1:1" } }
      3 {
        if ($favoriteStrong) { return [pscustomobject]@{ scores = @("1:2", "0:3"); upset = "1:1" } }
        return [pscustomobject]@{ scores = @("0:2", "1:2"); upset = "1:1" }
      }
      default { return [pscustomobject]@{ scores = @("1:3", "0:4"); upset = "2:2" } }
    }
  }

  if ($drawPressure -and $goals -le 2) { return [pscustomobject]@{ scores = @("1:1", "1:0"); upset = "0:1" } }
  switch ($goals) {
    0 { return [pscustomobject]@{ scores = @("0:0", "1:0"); upset = "0:1" } }
    1 { return [pscustomobject]@{ scores = @("1:0", "1:1"); upset = "0:1" } }
    2 {
      if ($balancedMatch) { return [pscustomobject]@{ scores = @("1:1", "2:1"); upset = "0:1" } }
      return [pscustomobject]@{ scores = @("2:0", "2:1"); upset = "1:1" }
    }
    3 {
      if ($favoriteStrong) { return [pscustomobject]@{ scores = @("2:1", "3:0"); upset = "1:1" } }
      return [pscustomobject]@{ scores = @("2:1", "2:0"); upset = "1:2" }
    }
    default { return [pscustomobject]@{ scores = @("3:1", "2:2"); upset = "1:2" } }
  }
}

function Get-FirstNonEmptyValue {
  param($Source, [string[]]$Names)

  if (-not $Source) { return $null }
  foreach ($name in $Names) {
    try { $value = $Source.PSObject.Properties[$name].Value } catch { $value = $null }
    if ($null -ne $value -and [string]$value -ne "") { return $value }
  }
  return $null
}

function Get-LiveResultFromMatch {
  param($Match)

  $homeGoals = Get-FirstNonEmptyValue $Match @("homeScore", "homeGoals", "homeGoal", "fullHomeScore", "homeTeamScore")
  $awayGoals = Get-FirstNonEmptyValue $Match @("awayScore", "awayGoals", "awayGoal", "fullAwayScore", "awayTeamScore")
  $status = [string](Get-FirstNonEmptyValue $Match @("matchStatus", "status"))

  if ($Match.result) {
    if ($null -eq $homeGoals) { $homeGoals = Get-FirstNonEmptyValue $Match.result @("homeGoals", "homeScore", "home") }
    if ($null -eq $awayGoals) { $awayGoals = Get-FirstNonEmptyValue $Match.result @("awayGoals", "awayScore", "away") }
    if (-not $status) { $status = [string](Get-FirstNonEmptyValue $Match.result @("status", "matchStatus")) }
  }

  if ($null -eq $homeGoals -or $null -eq $awayGoals) {
    return $null
  }

  return [pscustomobject]@{
    homeGoals = [int]$homeGoals
    awayGoals = [int]$awayGoals
    status = $(if ($status) { $status } else { "Finished" })
    source = "sporttery-live-api"
  }
}

function Should-UseLivePrediction {
  param($ExistingMatch, [switch]$RefreshPredictions)

  if ($RefreshPredictions -or -not $ExistingMatch -or -not $ExistingMatch.review) {
    return $true
  }
  return ([string]$ExistingMatch.review -match '^Auto-generated from Sporttery live odds:')
}

if (-not $OutFile) {
  $OutFile = Join-Path (Get-RootDir) ("data\" + $Date + ".json")
}

if ((Test-Path $OutFile) -and -not $Force -and -not $MergeExisting) {
  Write-Host "Data file already exists, keeping current file: $OutFile"
  exit 0
}

$targetDate = Get-TargetDateText $Date
$headers = @{
  "User-Agent" = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1"
  "Referer" = "https://m.sporttery.cn/mjc/jsq/zqzjq/"
  "Origin" = "https://m.sporttery.cn"
  "Accept" = "application/json, text/plain, */*"
  "Accept-Language" = "zh-CN,zh;q=0.9,en;q=0.8"
}
$apiUrl = "https://webapi.sporttery.cn/gateway/uniform/football/getMatchCalculatorV1.qry?channel=c&poolCode=$PoolCode"

Write-Host "Fetching Sporttery API: $apiUrl"
$response = Invoke-WebRequest -UseBasicParsing -Uri $apiUrl -Headers $headers
$apiPayload = $response.Content | ConvertFrom-Json

if ([string]$apiPayload.errorCode -ne "0" -or -not $apiPayload.value.matchInfoList) {
  throw "Sporttery API returned no usable match data."
}

$existingMatchMap = Get-ExistingMatchMap $OutFile
$existingPayload = Get-ExistingPayload $OutFile
$standingsLookup = Get-StandingsRowLookup $existingPayload
$matchList = New-Object System.Collections.Generic.List[object]

foreach ($group in @($apiPayload.value.matchInfoList)) {
  foreach ($match in @($group.subMatchList)) {
    if ([string]$match.matchDate -ne $targetDate) {
      continue
    }

    $matchCode = [string]$match.matchNum
    $codeMatch = [regex]::Match([string]$match.matchNumStr, "(\d{3})$")
    if ($codeMatch.Success) {
      $matchCode = $codeMatch.Groups[1].Value
    }

    $existingMatch = $null
    if ($existingMatchMap.ContainsKey([string]$match.matchId)) {
      $existingMatch = $existingMatchMap[[string]$match.matchId]
    }

    $context = Get-StandingsContext -Home ([string]$match.homeTeamAllName) -Away ([string]$match.awayTeamAllName) -StandingsLookup $standingsLookup
    $lean = Get-ResultLean -Had $match.had -Hhad $match.hhad -Context $context
    $goalPick = Get-TopGoalsPrediction -Ttg $match.ttg -Had $match.had -Hhad $match.hhad -Context $context
    $scorePick = Get-ScorePrediction -GoalLabel $goalPick.totalGoals -Lean $lean -Had $match.had -Hhad $match.hhad -Context $context

    $useLivePrediction = Should-UseLivePrediction -ExistingMatch $existingMatch -RefreshPredictions:$RefreshPredictions
    $leanText = switch ($lean) {
      "home" { "home" }
      "draw" { "draw" }
      "away" { "away" }
      default { $lean }
    }

    $predictionTotalGoals = $goalPick.totalGoals
    $predictionScores = @($scorePick.scores)
    $predictionUpset = $scorePick.upset
    $predictionConfidence = $goalPick.confidence
    if (-not $useLivePrediction -and $existingMatch -and $existingMatch.prediction) {
      if ($existingMatch.prediction.totalGoals) { $predictionTotalGoals = $existingMatch.prediction.totalGoals }
      if ($existingMatch.prediction.scores) { $predictionScores = @($existingMatch.prediction.scores) }
      if ($existingMatch.prediction.upset) { $predictionUpset = $existingMatch.prediction.upset }
      if ($existingMatch.prediction.confidence) { $predictionConfidence = $existingMatch.prediction.confidence }
    }

    $review = ('Auto-generated from Sporttery live odds: total-goals {0}, lean {1}, adjusted by hhad/crs/hafu and draw pressure.' -f $goalPick.totalGoals, $leanText)
    if (-not $useLivePrediction -and $existingMatch -and $existingMatch.review) {
      $review = $existingMatch.review
    }

    $resultData = Get-LiveResultFromMatch $match
    if (-not $resultData -and $existingMatch -and $existingMatch.result) {
      $resultData = $existingMatch.result
    }

    $postReview = $null
    if ($existingMatch -and $existingMatch.postReview) {
      $postReview = $existingMatch.postReview
    }

    $hadOdds = $null
    if ($match.had) {
      $hadUpdatedAt = [string]($match.had.updateDate) + ' ' + [string]($match.had.updateTime)
      $hadOdds = [pscustomobject]@{
        home = $match.had.h
        draw = $match.had.d
        away = $match.had.a
        updatedAt = $hadUpdatedAt
      }
    }

    $ttgOdds = $null
    if ($match.ttg) {
      $ttgUpdatedAt = [string]($match.ttg.updateDate) + ' ' + [string]($match.ttg.updateTime)
      $ttgOdds = [pscustomobject]@{
        s0 = $match.ttg.s0
        s1 = $match.ttg.s1
        s2 = $match.ttg.s2
        s3 = $match.ttg.s3
        s4 = $match.ttg.s4
        s5 = $match.ttg.s5
        s6 = $match.ttg.s6
        s7 = $match.ttg.s7
        updatedAt = $ttgUpdatedAt
      }
    }

    $hhadOdds = $null
    if ($match.hhad) {
      $hhadUpdatedAt = [string]($match.hhad.updateDate) + ' ' + [string]($match.hhad.updateTime)
      $hhadOdds = [pscustomobject]@{
        home = $match.hhad.h
        draw = $match.hhad.d
        away = $match.hhad.a
        handicap = $match.hhad.fixedOddsGoal
        updatedAt = $hhadUpdatedAt
      }
    }

    $crsOdds = $null
    if ($match.crs) {
      $crsUpdatedAt = [string]($match.crs.updateDate) + ' ' + [string]($match.crs.updateTime)
      $crsOdds = New-Object psobject
      foreach ($prop in @($match.crs.PSObject.Properties)) {
        if ($prop.Name -match '^s(\d{2})s(\d{2})$') {
          $homeScore = [int]$Matches[1]
          $awayScore = [int]$Matches[2]
          $scoreKey = ('{0}-{1}' -f $homeScore, $awayScore)
          Add-Member -InputObject $crsOdds -MemberType NoteProperty -Name $scoreKey -Value $prop.Value -Force
        }
      }
      Add-Member -InputObject $crsOdds -MemberType NoteProperty -Name 'homeOther' -Value $match.crs.s1sh -Force
      Add-Member -InputObject $crsOdds -MemberType NoteProperty -Name 'drawOther' -Value $match.crs.s1sd -Force
      Add-Member -InputObject $crsOdds -MemberType NoteProperty -Name 'awayOther' -Value $match.crs.s1sa -Force
      Add-Member -InputObject $crsOdds -MemberType NoteProperty -Name 'updatedAt' -Value $crsUpdatedAt
    }

    $hafuOdds = $null
    if ($match.hafu) {
      $hafuUpdatedAt = [string]($match.hafu.updateDate) + ' ' + [string]($match.hafu.updateTime)
      $hafuOdds = [pscustomobject]@{
        aa = $match.hafu.aa
        ad = $match.hafu.ad
        ah = $match.hafu.ah
        da = $match.hafu.da
        dd = $match.hafu.dd
        dh = $match.hafu.dh
        ha = $match.hafu.ha
        hd = $match.hafu.hd
        hh = $match.hafu.hh
        updatedAt = $hafuUpdatedAt
      }
    }

    $kickoffText = [string]($match.matchDate) + ' ' + [string]($match.matchTime)
    $predictionObject = [pscustomobject]@{
      totalGoals = $predictionTotalGoals
      scores = @($predictionScores)
      upset = $predictionUpset
      confidence = $predictionConfidence
      candidates = @($goalPick.candidates)
    }
    $oddsObject = [pscustomobject]@{
      had = $hadOdds
      ttg = $ttgOdds
      hhad = $hhadOdds
      crs = $crsOdds
      hafu = $hafuOdds
    }

    $matchObject = [pscustomobject]@{
      id = $matchCode
      matchNumStr = $match.matchNumStr
      matchId = [string]$match.matchId
      businessDate = $match.businessDate
      league = $match.leagueAllName
      leagueCode = $match.leagueCode
      leagueId = $match.leagueId
      groupName = $match.groupName
      kickoff = $kickoffText
      matchDate = $match.matchDate
      matchTime = $match.matchTime
      matchStatus = $match.matchStatus
      sellStatus = $match.sellStatus
      taxDateNo = $match.taxDateNo
      isHot = [bool]$match.isHot
      home = $match.homeTeamAllName
      homeCode = $match.homeTeamCode
      homeAbbr = $match.homeTeamAbbName
      homeRank = $match.homeRank
      away = $match.awayTeamAllName
      awayCode = $match.awayTeamCode
      awayAbbr = $match.awayTeamAbbName
      awayRank = $match.awayRank
      venue = $match.remark
      prediction = $predictionObject
      result = $resultData
      review = $review
      postReview = $postReview
      odds = $oddsObject
    }

    $matchList.Add($matchObject)
  }
}

if ($matchList.Count -eq 0) {
  throw "No Sporttery matches found for $targetDate."
}

$output = [ordered]@{
  date = $Date
  dateText = $targetDate
  source = "sporttery-live-api"
  fetchedAt = (Get-Date).ToString("s")
  lastUpdateTime = $apiPayload.value.lastUpdateTime
  apiPoolCode = $PoolCode
  matches = @($matchList.ToArray())
}

$outDir = Split-Path -Parent $OutFile
if (-not (Test-Path $outDir)) {
  New-Item -ItemType Directory -Force -Path $outDir | Out-Null
}

[pscustomobject]$output | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 $OutFile
Write-Host "Saved Sporttery data to $OutFile"
