# Build helper for ros2yolo workspace package
# - ensures a minimal pyproject.toml exists
# - runs colcon build for the package
# - falls back to an editable pip install if colcon fails

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
workspace="$(cd "$here/.." && pwd)"
pkg_dir="$here"
pyproject="$pkg_dir/pyproject.toml"

if [ ! -f "$pyproject" ]; then
	cat > "$pyproject" <<'EOF'
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"
EOF
	echo "Created $pyproject"
fi

cd "$workspace"
echo "Building workspace at: $workspace"

if command -v colcon >/dev/null 2>&1; then
	if colcon build --packages-select ros2yolo --event-handlers console_cohesion+; then
		echo "colcon build succeeded."
		exit 0
	else
		echo "colcon build failed; will attempt pip editable install as fallback."
	fi
else
	echo "colcon not found in PATH; attempting pip editable install."
fi

cd "$pkg_dir"
echo "Installing package via pip (editable mode) from: $pkg_dir"
# try modern editable config-settings first, then fallback
if pip install -e . --config-settings editable_mode=compat; then
	echo "pip editable install succeeded (editable_mode=compat)."
	exit 0
fi

if pip install -e .; then
	echo "pip editable install succeeded."
	exit 0
fi

echo "Build/install failed. Check output above for errors."
exit 1
