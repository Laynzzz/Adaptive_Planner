param([int]$RootProcessId, [int]$DurationSeconds = 900, [string]$OutputPath = 'docs/evidence/raw/http-load-process-samples.jsonl')
# Capture only the known load driver and its descendants; no command lines or secrets.
$watch = [System.Diagnostics.Stopwatch]::StartNew()
while ($watch.Elapsed.TotalSeconds -lt $DurationSeconds) {
    $known = [System.Collections.Generic.HashSet[int]]::new()
    [void]$known.Add($RootProcessId)
    $processRows = @(Get-CimInstance Win32_Process | Select-Object ProcessId, ParentProcessId, Name)
    do {
        $changed = $false
        foreach ($row in $processRows) {
            if ($known.Contains([int]$row.ParentProcessId) -and -not $known.Contains([int]$row.ProcessId)) {
                [void]$known.Add([int]$row.ProcessId)
                $changed = $true
            }
        }
    } while ($changed)
    $samples = @()
    foreach ($row in $processRows) {
        if (-not $known.Contains([int]$row.ProcessId)) { continue }
        $proc = Get-Process -Id $row.ProcessId -ErrorAction SilentlyContinue
        if ($null -ne $proc) {
            $samples += @{ process_id = $row.ProcessId; parent_id = $row.ParentProcessId; name = $row.Name; cpu_seconds = $proc.CPU; rss_bytes = $proc.WorkingSet64; lifetime_peak_rss_bytes = $proc.PeakWorkingSet64 }
        }
    }
    @{ utc = [DateTime]::UtcNow.ToString('o'); elapsed_seconds = $watch.Elapsed.TotalSeconds; processes = $samples } | ConvertTo-Json -Depth 5 -Compress | Add-Content -LiteralPath $OutputPath
    if (-not (Get-Process -Id $RootProcessId -ErrorAction SilentlyContinue)) { break }
    Start-Sleep -Seconds 5
}
