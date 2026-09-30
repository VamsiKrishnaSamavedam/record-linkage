$ErrorActionPreference = 'Stop'

$queuePath = 'outputs/review/marriage_parent_pair_sibling_discovery_queue_v1.csv'
$reviewDir = 'outputs/review'
$reportDir = 'outputs/reports'

if (-not (Test-Path -LiteralPath $queuePath)) {
    throw "Missing sibling-discovery queue: $queuePath"
}

New-Item -ItemType Directory -Path $reviewDir -Force | Out-Null
New-Item -ItemType Directory -Path $reportDir -Force | Out-Null

$queue = Import-Csv -LiteralPath $queuePath

$siblings = @($queue | Where-Object { $_.candidate_type -eq 'potential_sibling' } |
    Select-Object candidate_type, parent_pair_key, father_full_name_key, mother_full_name_key,
        marriage_identifier, marriage_event_date, spouse_role, spouse_gender,
        spouse_name_raw, spouse_lastname_raw, spouse_birth_date, spouse_birth_year, marriage_age_years,
        baptism_identifier, baptism_event_date, baptism_place_raw,
        child_name_raw, child_lastname_raw, child_birth_date, child_timing_year, child_timing_source,
        birth_year_gap, within_birth_window, birth_before_marriage_allowed, same_normalized_place,
        review_decision, review_reason, automatic_identity_cluster_change |
    Sort-Object parent_pair_key, marriage_identifier, baptism_identifier)

$selfLinks = @($queue | Where-Object { $_.candidate_type -eq 'possible_spouse_self_baptism' } |
    Select-Object candidate_type, parent_pair_key, father_full_name_key, mother_full_name_key,
        marriage_identifier, marriage_event_date, spouse_role, spouse_gender,
        spouse_name_raw, spouse_lastname_raw, spouse_birth_date, spouse_birth_year, marriage_age_years,
        baptism_identifier, baptism_event_date, baptism_place_raw,
        child_name_raw, child_lastname_raw, child_birth_date, child_timing_year, child_timing_source,
        birth_year_gap, within_birth_window, birth_before_marriage_allowed, same_normalized_place,
        review_decision, review_reason, automatic_identity_cluster_change |
    Sort-Object parent_pair_key, marriage_identifier, baptism_identifier)

$parentSummary = @($siblings | Group-Object parent_pair_key | ForEach-Object {
    $rows = $_.Group
    [pscustomobject]@{
        parent_pair_key = $_.Name
        father_full_name_key = $rows[0].father_full_name_key
        mother_full_name_key = $rows[0].mother_full_name_key
        potential_sibling_links = $rows.Count
        distinct_marriage_spouses = @($rows | ForEach-Object { "$($_.marriage_identifier): $($_.spouse_name_raw) $($_.spouse_lastname_raw)" } | Select-Object -Unique).Count
        distinct_baptism_children = @($rows | ForEach-Object { "$($_.baptism_identifier): $($_.child_name_raw)" } | Select-Object -Unique).Count
        earliest_child_timing_year = ($rows | ForEach-Object { [int]$_.child_timing_year } | Measure-Object -Minimum).Minimum
        latest_child_timing_year = ($rows | ForEach-Object { [int]$_.child_timing_year } | Measure-Object -Maximum).Maximum
        review_decision = 'needs_review'
        automatic_identity_cluster_change = $false
    }
} | Sort-Object -Property @{ Expression = 'potential_sibling_links'; Descending = $true }, @{ Expression = 'parent_pair_key'; Descending = $false })

$siblings | Export-Csv -LiteralPath (Join-Path $reviewDir 'professor_potential_siblings_with_parents_v1.csv') -NoTypeInformation -Encoding utf8
$selfLinks | Export-Csv -LiteralPath (Join-Path $reviewDir 'professor_spouse_baptism_links_for_review_v1.csv') -NoTypeInformation -Encoding utf8
$parentSummary | Export-Csv -LiteralPath (Join-Path $reportDir 'potential_sibling_parent_pair_summary_v1.csv') -NoTypeInformation -Encoding utf8

$summary = @(
    [pscustomobject]@{ metric = 'potential_sibling_rows'; value = $siblings.Count }
    [pscustomobject]@{ metric = 'parent_pairs_represented'; value = $parentSummary.Count }
    [pscustomobject]@{ metric = 'possible_spouse_baptism_rows'; value = $selfLinks.Count }
    [pscustomobject]@{ metric = 'automatic_identity_cluster_changes'; value = 0 }
)
$summary | Export-Csv -LiteralPath (Join-Path $reportDir 'professor_sibling_review_package_summary_v1.csv') -NoTypeInformation -Encoding utf8

Write-Output "Potential sibling rows: $($siblings.Count)"
Write-Output "Parent pairs represented: $($parentSummary.Count)"
Write-Output "Spouse-baptism rows: $($selfLinks.Count)"
