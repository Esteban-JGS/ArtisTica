#!/usr/bin/env bash
# Reglas del repositorio que el CI hace cumplir. Se corre desde la raiz:
#   bash .github/scripts/reglas-del-repositorio.sh
# Con BASE_SHA y HEAD_SHA definidos revisa tambien los commits de ese rango.
set -euo pipefail

# Comparacion por bytes: los patrones son UTF-8 escrito con escapes
export LC_ALL=C

GUION_LARGO=$'\xE2\x80\x94'
GUION_MEDIO=$'\xE2\x80\x93'

# .claude/ queda afuera: su skill de documentacion trae los guiones a proposito
RUTAS=(backend docs orquestacion .agents .github AGENTS.md CLAUDE.md)
EXCLUIDOS=(':(exclude)*.docx' ':(exclude)**/package-lock.json')

fallas=0

revisar_commits() {
  local base="${BASE_SHA:-}" cabeza="${HEAD_SHA:-}"
  if [[ -z "$base" || -z "$cabeza" ]]; then
    echo "Commits: sin BASE_SHA y HEAD_SHA, no se revisan"
    return
  fi
  local sha shas mensaje encontrados=0
  # Asignacion aparte para que un rango invalido corte el script
  shas=$(git rev-list "$base..$cabeza")
  for sha in $shas; do
    # El nombre del archivo CLAUDE.md no cuenta como mencion: se quita antes
    mensaje=$(git log -1 --format=%B "$sha" | sed -E 's/claude\.md//Ig')
    if grep -qiE 'co-authored-by|claude' <<<"$mensaje"; then
      echo "Commit con coautor o mencion a una herramienta de asistencia:"
      git log -1 --format='  %h %s' "$sha"
      grep -iE 'co-authored-by|claude' <<<"$mensaje" | sed 's/^/    /'
      encontrados=1
    fi
  done
  if ((encontrados)); then
    fallas=1
  else
    echo "Commits: sin coautores ni menciones en $base..$cabeza"
  fi
}

revisar_guiones() {
  local salida estado=0
  salida=$(git grep -n -I -F -e "$GUION_LARGO" -e "$GUION_MEDIO" \
    -- "${RUTAS[@]}" "${EXCLUIDOS[@]}") || estado=$?
  # git grep: 0 encontro, 1 no encontro, otro valor es un error
  case $estado in
    0)
      echo "Guiones largos o medios (archivo:linea):"
      echo "$salida" | cut -d: -f1,2 | sed 's/^/  /'
      fallas=1
      ;;
    1) echo "Guiones: ninguno en ${RUTAS[*]}" ;;
    *)
      echo "git grep fallo con codigo $estado"
      exit "$estado"
      ;;
  esac
}

revisar_commits
revisar_guiones

if ((fallas)); then
  echo "Reglas del repositorio: FALLA"
  exit 1
fi
echo "Reglas del repositorio: OK"
