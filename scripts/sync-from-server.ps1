<#
.SYNOPSIS
    Sincroniza archivos generados por los agentes desde el servidor a tu vault de Obsidian.

.DESCRIPTION
    Copia notas de Obsidian (vault) y logs desde el servidor remoto.
    Las notas se sincronizan directamente al vault de Obsidian (Segundo cerebro).
    Los logs se guardan en la carpeta del proyecto.

.PARAMETER Target
    Que sincronizar: vault, logs, all (default: all)

.PARAMETER Overwrite
    Si se especifica, borra los archivos locales de cada carpeta del vault antes
    de copiar todo nuevamente desde el servidor.

.EXAMPLE
    .\scripts\sync-from-server.ps1                 # sincroniza todo
    .\scripts\sync-from-server.ps1 -Target vault   # solo notas de Obsidian
    .\scripts\sync-from-server.ps1 -Target logs    # solo logs
    .\scripts\sync-from-server.ps1 -Target vault -Overwrite  # reemplaza vault local
#>

param(
    [ValidateSet("vault", "logs", "all")]
    [string]$Target = "all",
    [switch]$Overwrite
)

$ErrorActionPreference = "Stop"

# Configuracion
$SERVER = "danilo@192.168.100.18"
$REMOTE_BASE = "~/personal-agent"
$LOCAL_BASE = Split-Path -Parent $PSScriptRoot

# Vault de Obsidian (Segundo cerebro)
$OBSIDIAN_VAULT = "D:\OneDrive - Universidad Nacional Jorge Basadre Grohmann\Archivos importantes\Segundo cerebro"

# Carpetas del servidor que se sincronizan al vault
$VAULT_FOLDERS = @(
    @{ Remote = "vault/Agent-Research/Papers";         Local = "Agent-Research\Papers" },
    @{ Remote = "vault/Agent-Research/Ideas";          Local = "Agent-Research\Ideas" },
    @{ Remote = "vault/Agent-Research/YouTube";        Local = "Agent-Research\YouTube" },
    @{ Remote = "vault/Agent-Research/FB-Marketplace"; Local = "Agent-Research\FB-Marketplace" }
)

function Sync-Folder {
    param(
        [string]$RemotePath,
        [string]$LocalPath,
        [string]$Label
    )

    if (-not (Test-Path $LocalPath)) {
        New-Item -ItemType Directory -Path $LocalPath -Force | Out-Null
    }

    Write-Host "[sync] $Label" -ForegroundColor Cyan
    Write-Host "   $SERVER`:$RemotePath -> $LocalPath" -ForegroundColor DarkGray

    scp -r "${SERVER}:${RemotePath}/*" "$LocalPath/" 2>&1
    if ($LASTEXITCODE -eq 0) {
        $count = (Get-ChildItem -Path $LocalPath -Recurse -File).Count
        Write-Host "   OK $Label sincronizado ($count archivos)" -ForegroundColor Green
    } else {
        Write-Host "   ERROR sincronizando $Label" -ForegroundColor Yellow
    }
}

function Sync-VaultFolder {
    param(
        [string]$RemotePath,
        [string]$LocalPath,
        [string]$Label,
        [switch]$Overwrite
    )

    if (-not (Test-Path $LocalPath)) {
        New-Item -ItemType Directory -Path $LocalPath -Force | Out-Null
    }

    $remoteFiles = ssh $SERVER "ls $RemotePath/ 2>/dev/null" 2>$null
    if (-not $remoteFiles) {
        Write-Host "   SKIP $Label - vacio" -ForegroundColor DarkGray
        return @{
            New = 0
            Skipped = 0
            Replaced = 0
        }
    }

    $remoteList = $remoteFiles -split "`n" | Where-Object { $_.Trim() -ne "" }

    if ($Overwrite) {
        Get-ChildItem -Path $LocalPath -File -ErrorAction SilentlyContinue | Remove-Item -Force

        Write-Host "   REPLACE $Label - copiando $($remoteList.Count) archivos..." -ForegroundColor Yellow
        scp -r "${SERVER}:${RemotePath}/*" "$LocalPath/" 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "      OK $($remoteList.Count) archivos copiados" -ForegroundColor Green
            return @{
                New = 0
                Skipped = 0
                Replaced = $remoteList.Count
            }
        }

        Write-Host "      ERROR sincronizando $Label" -ForegroundColor Yellow
        return @{
            New = 0
            Skipped = 0
            Replaced = 0
        }
    }

    $newFiles = @()
    foreach ($f in $remoteList) {
        $f = $f.Trim()
        $localFile = Join-Path $LocalPath $f
        if (-not (Test-Path $localFile)) {
            $newFiles += $f
        }
    }

    if ($newFiles.Count -eq 0) {
        Write-Host "   OK $Label - al dia ($($remoteList.Count) archivos)" -ForegroundColor DarkGray
        return @{
            New = 0
            Skipped = $remoteList.Count
            Replaced = 0
        }
    }

    Write-Host "   COPY $Label - descargando $($newFiles.Count) nuevos (de $($remoteList.Count))..." -ForegroundColor Cyan
    $copied = 0
    foreach ($f in $newFiles) {
        scp "${SERVER}:${RemotePath}/${f}" "$LocalPath/" 2>$null
        if ($LASTEXITCODE -eq 0) {
            $copied++
        }
    }
    Write-Host "      OK $copied archivos nuevos" -ForegroundColor Green

    return @{
        New = $copied
        Skipped = $remoteList.Count - $newFiles.Count
        Replaced = 0
    }
}

Write-Host ""
Write-Host "Sincronizacion desde servidor ($SERVER)" -ForegroundColor White
Write-Host "   $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor DarkGray
Write-Host ""

if ($Target -in @("vault", "all")) {
    Write-Host "Sincronizando notas al vault de Obsidian..." -ForegroundColor Cyan
    Write-Host "   Destino: $OBSIDIAN_VAULT" -ForegroundColor DarkGray
    if ($Overwrite) {
        Write-Host "   Modo overwrite: se reemplazaran los archivos locales del vault" -ForegroundColor Yellow
    }
    Write-Host ""

    $totalNew = 0
    $totalSkipped = 0
    $totalReplaced = 0

    foreach ($folder in $VAULT_FOLDERS) {
        $remotePath = "$REMOTE_BASE/$($folder.Remote)"
        $localPath  = Join-Path $OBSIDIAN_VAULT $folder.Local
        $label      = $folder.Local

        $result = Sync-VaultFolder `
            -RemotePath $remotePath `
            -LocalPath $localPath `
            -Label $label `
            -Overwrite:$Overwrite

        $totalNew += $result.New
        $totalSkipped += $result.Skipped
        $totalReplaced += $result.Replaced
    }

    Write-Host ""
    if ($Overwrite) {
        Write-Host "   Resumen: $totalReplaced archivos reemplazados" -ForegroundColor White
    } else {
        Write-Host "   Resumen: $totalNew nuevos, $totalSkipped ya existian" -ForegroundColor White
    }
}

if ($Target -in @("logs", "all")) {
    Sync-Folder `
        -RemotePath "$REMOTE_BASE/logs" `
        -LocalPath "$LOCAL_BASE\logs" `
        -Label "Logs"
}

Write-Host ""
Write-Host "Sincronizacion completada" -ForegroundColor Green
Write-Host ""
