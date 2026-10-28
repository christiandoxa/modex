if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    echo 'source scripts/ci/private-scratch.sh from a CI entrypoint.' >&2
    exit 2
fi

if [[ ! -d /tmp || -L /tmp ]]; then
    echo 'CI scratch requires a real /tmp directory.' >&2
    return 1
fi
read -r tmp_mode tmp_owner < <(stat -c '%a %u' -- /tmp)
if [[ "$tmp_mode" != 1777 || "$tmp_owner" != 0 ]]; then
    echo "CI scratch requires root-owned sticky /tmp; found mode=$tmp_mode owner=$tmp_owner." >&2
    return 1
fi

umask 077
MODEX_CI_PRIVATE_ROOT="$(mktemp -d --tmpdir=/tmp modex-ci-private.XXXXXXXXXX)"
MODEX_CI_PRIVATE_ROOT_CREATED="$MODEX_CI_PRIVATE_ROOT"

modex_ci_cleanup_private_scratch() {
    case "$MODEX_CI_PRIVATE_ROOT_CREATED" in
        /tmp/modex-ci-private.*) rm -rf -- "$MODEX_CI_PRIVATE_ROOT_CREATED" ;;
        *) echo 'Refusing to remove an unexpected CI scratch path.' >&2; return 1 ;;
    esac
}

trap modex_ci_cleanup_private_scratch EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

mkdir -m 700 -- \
    "$MODEX_CI_PRIVATE_ROOT/home" \
    "$MODEX_CI_PRIVATE_ROOT/tmp" \
    "$MODEX_CI_PRIVATE_ROOT/config" \
    "$MODEX_CI_PRIVATE_ROOT/cache" \
    "$MODEX_CI_PRIVATE_ROOT/data" \
    "$MODEX_CI_PRIVATE_ROOT/state"

export MODEX_CI_PRIVATE_ROOT
export HOME="$MODEX_CI_PRIVATE_ROOT/home"
export TMPDIR="$MODEX_CI_PRIVATE_ROOT/tmp"
export TMP="$TMPDIR"
export TEMP="$TMPDIR"
export XDG_CONFIG_HOME="$MODEX_CI_PRIVATE_ROOT/config"
export XDG_CACHE_HOME="$MODEX_CI_PRIVATE_ROOT/cache"
export XDG_DATA_HOME="$MODEX_CI_PRIVATE_ROOT/data"
export XDG_STATE_HOME="$MODEX_CI_PRIVATE_ROOT/state"
