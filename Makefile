MOJO ?= mojo
MOJO_VERSION := Mojo 1.2.0 (2016d0cd)
MOJO_FLAGS := -O3 --target-cpu=x86-64-v3

.PHONY: build check-toolchain probes test

check-toolchain:
	@test "$$($(MOJO) --version)" = "$(MOJO_VERSION)" || { echo 'Pinned toolchain required: $(MOJO_VERSION)' >&2; exit 1; }

build: check-toolchain
	mkdir -p build
	$(MOJO) build $(MOJO_FLAGS) -I src src/main.mojo -o build/modex

probes: check-toolchain
	mkdir -p build/probes
	$(MOJO) build $(MOJO_FLAGS) probes/platform.mojo -o build/probes/platform
	MODEX_PROBE_SENTINEL=isolated-probe build/probes/platform $(CURDIR)/build/probes/platform-files
	$(MOJO) build $(MOJO_FLAGS) probes/process.mojo -o build/probes/process
	build/probes/process
	$(MOJO) build $(MOJO_FLAGS) probes/socket.mojo -o build/probes/socket
	build/probes/socket

test: build
	python3 -m unittest discover -s tests -p 'test_*.py' -v
