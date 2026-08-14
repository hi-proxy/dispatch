#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
scratch_dir="$project_dir/.build"
app_dir="$project_dir/build/Dispatch.app"
contents_dir="$app_dir/Contents"
module_cache="/private/tmp/dispatch-swift-module-cache"

env CLANG_MODULE_CACHE_PATH="$module_cache" \
  swift build --package-path "$project_dir" --scratch-path "$scratch_dir" -c release

mkdir -p "$contents_dir/MacOS" "$contents_dir/Resources"
install -m 755 "$scratch_dir/release/DispatchMac" "$contents_dir/MacOS/DispatchMac"
install -m 644 "$project_dir/Resources/Info.plist" "$contents_dir/Info.plist"
codesign --force --sign - "$app_dir"

echo "$app_dir"
