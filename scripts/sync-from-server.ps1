<#
.SYNOPSIS
    Sincroniza archivos generados por los agentes desde el servidor a tu vault de Obsidian.

.DESCRIPTION
    Copia notas de Obsidian (vault) y logs desde el servidor remoto.
    Las notas se sincronizan directamente al vault de Obsidian (Segundo cerebro).
    Los logs se guardan en la carpeta del proyecto.

.PARAMETER Target
    Qué sincronizar: vault, logs, all (default: all)

.EXAMPLE
    .\scripts\sync-from-server.ps1              # sincroniza todo
    .\scripts\sync-from-server.ps1 -Target vault  # solo notas de Obsidian
    .\scripts\sync-from-server.ps1 -Target logs    # solo logs
#>

param(
    [ValidateSet("vault", "logs", "all")]
    [string]$Target = "all"
)

$ErrorActionPreference = "Stop"

# ── Configuración ────────────────────────────────────────────────────────────
$SERVER = "danilo@192.168.100.18"
$REMOTE_BASE = "~/personal-agent"
$LOCAL_BASE = Split-Path -Parent $PSScriptRoot   # raíz del proyecto

# Vault de Obsidian (Segundo cerebro)
$OBSIDIAN_VAULT = "D:\OneDrive - Universidad Nacional Jorge Basadre Grohmann\Archivos importantes\Segundo cerebro"

# Carpetas del servidor que se sincronizan al vault
$VAULT_FOLDERS = @(
    @{ Remote = "vault/Agent-Research/Papers";         Local = "Agent-Research\Papers" },
    @{ Remote = "vault/Agent-Research/Ideas";          Local = "Agent-Research\Ideas" },
    @{ Remote = "vault/Agent-Research/YouTube";        Local = "Agent-Research\YouTube" },
    @{ Remote = "vault/Agent-Research/FB-Marketplace"; Local = "Agent-Research\FB-Marketplace" }
)

# ── Funciones ────────────────────────────────────────────────────────────────

function Sync-Folder {
    param(
        [string]$RemotePath,
        [string]$LocalPath,
        [string]$Label
    )

    if (-not (Test-Path $LocalPath)) {
        New-Item -ItemType Directory -Path $LocalPath -Force | Out-Null
    }

    Write-Host "📥 Sincronizando $Label..." -ForegroundColor Cyan
    Write-Host "   $SERVER`:$RemotePath → $LocalPath" -ForegroundColor DarkGray

    # Usar scp recursivo (compatible con Windows sin rsync)
    scp -r "${SERVER}:${RemotePath}/*" "$LocalPath/" 2>&1
    if ($LASTEXITCODE -eq 0) {
        $count = (Get-ChildItem -Path $LocalPath -Recurse -File).Count
        Write-Host "   ✅ $Label sincronizado ($count archivos)" -ForegroundColor Green
    } else {
        Write-Host "   ⚠️  Error sincronizando $Label" -ForegroundColor Yellow
    }
}

# ── Ejecución ────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "🔄 Sincronización desde servidor ($SERVER)" -ForegroundColor White
Write-Host "   $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor DarkGray
Write-Host ""

if ($Target -in @("vault", "all")) {
    Write-Host "📥 Sincronizando notas al vault de Obsidian..." -ForegroundColor Cyan
    Write-Host "   Destino: $OBSIDIAN_VAULT" -ForegroundColor DarkGray
    Write-Host ""

    $totalNew = 0
    $totalSkipped = 0

    foreach ($folder in $VAULT_FOLDERS) {
        $remotePath = "$REMOTE_BASE/$($folder.Remote)"
        $localPath  = Join-Path $OBSIDIAN_VAULT $folder.Local
        $label      = $folder.Local

        if (-not (Test-Path $localPath)) {
            New-Item -ItemType Directory -Path $localPath -Force | Out-Null
        }

        # Obtener lista de archivos remotos
        $remoteFiles = ssh $SERVER "ls $remotePath/ 2>/dev/null" 2>$null
        if (-not $remoteFiles) {
            Write-Host "   ⏭️  $label — vacío" -ForegroundColor DarkGray
            continue
        }
        $remoteList = $remoteFiles -split "`n" | Where-Object { $_.Trim() -ne "" }

        # Solo copiar archivos que no existen localmente
        $newFiles = @()
        foreach ($f in $remoteList) {
            $f = $f.Trim()
            $localFile = Join-Path $localPath $f
            if (-not (Test-Path $localFile)) {
                $newFiles += $f
            }
        }

        if ($newFiles.Count -eq 0) {
            $totalSkipped += $remoteList.Count
            Write-Host "   ✅ $label — al día ($($remoteList.Count) archivos)" -ForegroundColor DarkGray
            continue
        }

        # Copiar solo archivos nuevos
        Write-Host "   📄 $label — descargando $($newFiles.Count) nuevos (de $($remoteList.Count))..." -ForegroundColor Cyan
        foreach ($f in $newFiles) {
            scp "${SERVER}:${remotePath}/${f}" "$localPath/" 2>$null
            if ($LASTEXITCODE -eq 0) {
                $totalNew++
            }
        }
        Write-Host "      ✅ $($newFiles.Count) archivos nuevos" -ForegroundColor Green
    }

    Write-Host ""
    Write-Host "   📊 Resumen: $totalNew nuevos, $totalSkipped ya existían" -ForegroundColor White
}

if ($Target -in @("logs", "all")) {
    Sync-Folder `
        -RemotePath "$REMOTE_BASE/logs" `
        -LocalPath "$LOCAL_BASE\logs" `
        -Label "Logs"
}

Write-Host ""
Write-Host "✅ Sincronización completada" -ForegroundColor Green
Write-Host ""
