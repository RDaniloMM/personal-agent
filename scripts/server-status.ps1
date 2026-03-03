<#
.SYNOPSIS
    Muestra el estado de los workers y logs recientes del servidor.

.PARAMETER Worker
    Ver logs de un worker específico: fb, yt, arxiv (default: muestra status de todos)

.PARAMETER Lines
    Número de líneas de log a mostrar (default: 30)

.EXAMPLE
    .\scripts\server-status.ps1              # status de todos los contenedores
    .\scripts\server-status.ps1 -Worker fb    # logs recientes del fb-worker
    .\scripts\server-status.ps1 -Worker yt -Lines 50
#>

param(
    [ValidateSet("fb", "yt", "arxiv", "")]
    [string]$Worker = "",

    [int]$Lines = 30
)

$SERVER = "danilo@192.168.100.18"
$REMOTE_BASE = "~/personal-agent"

Write-Host ""
Write-Host "📊 Estado del servidor ($SERVER)" -ForegroundColor White
Write-Host "   $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor DarkGray
Write-Host ""

# Siempre mostrar containers
Write-Host "🐳 Contenedores:" -ForegroundColor Cyan
ssh $SERVER "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>&1"
Write-Host ""

# Uso de disco
Write-Host "💾 Espacio en disco:" -ForegroundColor Cyan
ssh $SERVER "df -h / | tail -1; echo ''; du -sh $REMOTE_BASE/vault $REMOTE_BASE/logs 2>/dev/null"
Write-Host ""

# Logs si se especifica worker
if ($Worker) {
    $containerMap = @{
        "fb"    = "personal-agent-fb"
        "yt"    = "personal-agent-yt"
        "arxiv" = "personal-agent-arxiv"
    }
    $container = $containerMap[$Worker]

    Write-Host "📋 Últimas $Lines líneas de $container`:" -ForegroundColor Cyan
    ssh $SERVER "docker logs $container --tail $Lines 2>&1"
}

# Contar notas
Write-Host ""
Write-Host "📝 Notas en vault:" -ForegroundColor Cyan
ssh $SERVER "find $REMOTE_BASE/vault -name '*.md' | wc -l | xargs -I{} echo '   Total: {} archivos .md'; for d in $REMOTE_BASE/vault/Agent-Research/*/; do name=`$(basename `$d); count=`$(find `$d -name '*.md' | wc -l); echo ""   `$name: `$count""; done"

Write-Host ""
