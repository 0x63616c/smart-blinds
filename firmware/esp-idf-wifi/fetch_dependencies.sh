#!/bin/sh
set -eu
repo_root=$(git rev-parse --show-toplevel)
vendor_dir="$repo_root/work/wifi-idf-extra"
if [ ! -d "$vendor_dir/.git" ]; then
  git clone --filter=blob:none --no-checkout https://github.com/espressif/idf-extra-components.git "$vendor_dir"
fi
# The dependency directory belongs only to this evaluation target.
git -C "$vendor_dir" checkout --detach cad43839020fc329722035a35640a54e06fee09b
git -C "$vendor_dir" submodule update --init coap/libcoap
test "$(git -C "$vendor_dir/coap/libcoap" rev-parse HEAD)" = d9b4031ee61df1a40ecec46fe3817a1f985b3919
git -C "$vendor_dir" diff --exit-code HEAD -- coap
git -C "$vendor_dir/coap/libcoap" diff --exit-code HEAD --
