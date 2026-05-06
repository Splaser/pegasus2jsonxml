$srcRoot = "F:\roms"
$dstRoot = ".\Resource"
$report = @()

Get-ChildItem -Path $srcRoot -Directory | ForEach-Object {
    $platformName = $_.Name
    $srcMeta = Join-Path $_.FullName "metadata.pegasus.txt"
    $dstDir = Join-Path $dstRoot $platformName
    $dstMeta = Join-Path $dstDir "metadata.pegasus.txt"

    if (Test-Path $srcMeta) {
        New-Item -ItemType Directory -Force -Path $dstDir | Out-Null
        Copy-Item -Path $srcMeta -Destination $dstMeta -Force

        $srcInfo = Get-Item $srcMeta
        $dstInfo = Get-Item $dstMeta

        $report += [PSCustomObject]@{
            Platform = $platformName
            Status = "UPDATED"
            Source = $srcMeta
            Destination = $dstMeta
            Size = $srcInfo.Length
            SourceModified = $srcInfo.LastWriteTime
            DestModified = $dstInfo.LastWriteTime
        }

        Write-Host "[UPDATED] $platformName"
    } else {
        $report += [PSCustomObject]@{
            Platform = $platformName
            Status = "NO_METADATA"
            Source = $srcMeta
            Destination = ""
            Size = ""
            SourceModified = ""
            DestModified = ""
        }

        Write-Host "[SKIP] $platformName - no metadata.pegasus.txt"
    }
}

$report | Export-Csv ".\metadata_sync_report.csv" -NoTypeInformation -Encoding UTF8