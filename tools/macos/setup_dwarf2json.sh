#!/usr/bin/env bash
# Install Go (user-level, no sudo) and build dwarf2json for XNU ISF generation.
set -uo pipefail
LOG=~/d2j_setup.log; SENT=~/d2j_setup.sentinel
rm -f "$SENT"; exec > "$LOG" 2>&1

cd ~
if [ ! -x ~/go-dist/go/bin/go ]; then
  echo "=== [$(date)] fetch Go ==="
  GOVER=$(curl -fsSL "https://go.dev/VERSION?m=text" | head -1)
  echo "Go version: $GOVER"
  curl -fsSL "https://go.dev/dl/${GOVER}.linux-amd64.tar.gz" -o /tmp/go.tgz || { echo GO_DL_FAIL; echo FAIL>"$SENT"; exit 1; }
  rm -rf ~/go-dist && mkdir -p ~/go-dist && tar -C ~/go-dist -xzf /tmp/go.tgz
fi
export PATH="$HOME/go-dist/go/bin:$PATH"
export GOPATH="$HOME/go-path"
go version

echo "=== [$(date)] clone + build dwarf2json ==="
[ -d ~/dwarf2json/.git ] || git clone https://github.com/volatilityfoundation/dwarf2json.git ~/dwarf2json
cd ~/dwarf2json
go build -o ~/dwarf2json/dwarf2json . || { echo BUILD_FAIL; echo FAIL>"$SENT"; exit 1; }
~/dwarf2json/dwarf2json --help 2>&1 | head -5 || true
echo "=== [$(date)] DONE ==="
ls -la ~/dwarf2json/dwarf2json
echo OK > "$SENT"
