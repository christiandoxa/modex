MOJO ?= mojo
MOJO_VERSION := Mojo 1.2.0 (2016d0cd)
MOJO_FLAGS := -O3 --target-cpu=x86-64-v3
BUILD_DIR ?= build
BUILD_ROOT := $(shell realpath -m -- "$(BUILD_DIR)")
PYTHON ?= python3

.PHONY: build build-internal check-toolchain probes test test-run-internal unit unit-build unit-compile unit-run-internal unit-compile-internal FORCE_UNIT_BUILD_STATE FORCE_UNIT_TARGET_CHECK ci-bootstrap ci-fast ci-full ci-parity ci-validate ci-dependencies

check-toolchain:
	@test "$$($(MOJO) --version)" = "$(MOJO_VERSION)" || { echo 'Pinned toolchain required: $(MOJO_VERSION)' >&2; exit 1; }

build: check-toolchain
	@mkdir -p -- "$(BUILD_ROOT)/.modex"
	+flock --exclusive --close "$(UNIT_BUILD_LOCK)" $(MAKE) --no-print-directory build-internal

build-internal:
	mkdir -p $(BUILD_ROOT)
	$(MOJO) build $(MOJO_FLAGS) -I src src/main.mojo -o $(BUILD_ROOT)/modex

probes: check-toolchain
	mkdir -p $(BUILD_ROOT)/probes
	$(MOJO) build $(MOJO_FLAGS) probes/platform.mojo -o $(BUILD_ROOT)/probes/platform
	MODEX_PROBE_SENTINEL=isolated-probe $(BUILD_ROOT)/probes/platform $(BUILD_ROOT)/probes/platform-files
	$(MOJO) build $(MOJO_FLAGS) probes/process.mojo -o $(BUILD_ROOT)/probes/process
	$(BUILD_ROOT)/probes/process
	$(MOJO) build $(MOJO_FLAGS) -I src probes/process_spawn.mojo -o $(BUILD_ROOT)/probes/process_spawn
	$(BUILD_ROOT)/probes/process_spawn
	$(MOJO) build $(MOJO_FLAGS) probes/socket.mojo -o $(BUILD_ROOT)/probes/socket
	$(BUILD_ROOT)/probes/socket

# Each local Mojo source is an input: Mojo 1.2 does not emit import depfiles.
MODEX_UNIT_JOBS ?= 4
UNIT_BUILD_PROGRAMS ?= \
	test_provider_sse_wire \
	test_provider_sse_json \
	provider_sse_driver \
	test_provider_chat_chunk \
	provider_chat_chunk_driver \
	test_provider_sse_events \
	test_provider_chat_usage \
	test_provider_chat_tools \
	test_uuid7 \
	test_provider_chat_items \
	test_rtk_command \
	test_provider_chat_metadata \
	test_provider_chat_stream \
	test_provider_chat_reader \
	provider_chat_stream_driver \
	test_provider_request_messages \
	test_provider_request_prepare \
	test_provider_request_tools \
	test_provider_request_params \
	test_provider_request \
	provider_request_driver \
	test_provider_chat_buffered \
	provider_chat_buffered_driver \
	test_provider_deepseek_transport \
	test_provider_rate_limits \
	provider_deepseek_transport_driver \
	test_provider_conversations \
	test_provider_passthrough \
	provider_passthrough_driver \
	test_runtime_observer \
	test_runtime_recovery \
	test_quota_handoff_04392 \
	runtime_recovery_driver \
	test_inspection_cli \
	test_gateway_cli \
	test_super_cli \
	local_rewrite_driver \
	test_json \
	test_json_float \
	test_sha256 \
	sha256_driver \
	loopback_http_driver \
	loopback_http_stream_driver \
	loopback_server_driver \
	test_sessions \
	test_session_cli \
	test_local_time \
	json_driver \
	test_zstd \
	zstd_driver \
	text_driver \
	width_memory_driver \
	log_text_driver \
	log_transcript_driver \
	log_payload_driver \
	log_payload_render_driver \
	unicode_properties_driver \
	test_toml \
	toml_driver \
	test_log_time \
	log_time_driver \
	test_log_follow \
	test_log_follow_paths \
	test_log_operational \
	test_log_transcript_events \
	test_log_sources \
	test_app_server_args \
	app_server_args_driver \
	app_server_rpc_driver \
	test_app_server_rpc \
	test_super_hooks \
	super_hooks_driver \
	process_wait_child \
	test_process_wait \
	process_stdio_child \
	test_process_stdio \
	process_capture_child \
	test_process_capture \
	process_child \
	test_process_spawn
UNIT_RUNS ?= \
	test_provider_sse_wire \
	test_provider_sse_json \
	test_provider_chat_chunk \
	test_provider_sse_events \
	test_provider_chat_usage \
	test_provider_chat_tools \
	test_uuid7 \
	test_provider_chat_items \
	test_rtk_command \
	test_provider_chat_metadata \
	test_provider_chat_stream \
	test_provider_chat_reader \
	test_provider_request_messages \
	test_provider_request_prepare \
	test_provider_request_tools \
	test_provider_request_params \
	test_provider_request \
	test_provider_chat_buffered \
	test_provider_deepseek_transport \
	test_provider_rate_limits \
	test_provider_conversations \
	test_provider_passthrough \
	test_runtime_observer \
	test_runtime_recovery \
	test_quota_handoff_04392 \
	test_inspection_cli \
	test_gateway_cli \
	test_super_cli \
	test_json \
	test_json_float \
	test_sha256 \
	test_sessions \
	test_session_cli \
	test_local_time \
	test_zstd \
	test_toml \
	test_log_time \
	test_log_follow:log-follow-files \
	test_log_follow_paths:follow-paths \
	test_log_operational \
	test_log_transcript_events \
	test_log_sources \
	test_app_server_args \
	test_app_server_rpc \
	test_super_hooks \
	test_process_wait:process_wait_child \
	test_process_stdio:process_stdio_child \
	test_process_capture:process_capture_child \
	test_process_spawn:process_child
UNIT_BUILD_TARGETS = $(addprefix $(BUILD_ROOT)/tests/,$(UNIT_BUILD_PROGRAMS))
UNIT_BUILD_STATE = $(BUILD_ROOT)/.modex/unit-build-state
UNIT_BUILD_LOCK = $(BUILD_ROOT)/.modex/unit-build.lock

unit: check-toolchain
	@mkdir -p -- "$(BUILD_ROOT)/.modex"
	+flock --exclusive --close "$(UNIT_BUILD_LOCK)" $(MAKE) --no-print-directory --jobs=$(MODEX_UNIT_JOBS) unit-run-internal

unit-run-internal: unit-compile-internal
	@set -eu; \
	for run in $(UNIT_RUNS); do \
		executable="$${run%%:*}"; \
		case "$$run" in \
			*:* ) argument="$${run#*:}"; "$(BUILD_ROOT)/tests/$$executable" "$(BUILD_ROOT)/tests/$$argument" ;; \
			* ) "$(BUILD_ROOT)/tests/$$executable" ;; \
		esac; \
	done

unit-build: check-toolchain
	@mkdir -p -- "$(BUILD_ROOT)/.modex"
	+flock --exclusive --close "$(UNIT_BUILD_LOCK)" $(MAKE) --no-print-directory --jobs=$(MODEX_UNIT_JOBS) unit-compile-internal

unit-compile: unit-build

unit-compile-internal: $(UNIT_BUILD_TARGETS)

FORCE_UNIT_BUILD_STATE FORCE_UNIT_TARGET_CHECK:

$(UNIT_BUILD_STATE): FORCE_UNIT_BUILD_STATE
	@scripts/ci/update-unit-build-state.sh "$@" "$(MOJO)" "$(MOJO_VERSION)" "$(MOJO_FLAGS)" "-I src"

$(UNIT_BUILD_TARGETS): $(BUILD_ROOT)/tests/%: tests/%.mojo $(UNIT_BUILD_STATE) FORCE_UNIT_TARGET_CHECK
	scripts/ci/build-unit-target.sh "$@" "$<" "$(UNIT_BUILD_STATE)" "$(UNIT_BUILD_STATE).outputs/$(@F).meta" "$(MOJO)" "$(MOJO_FLAGS)" "-I src"

test: check-toolchain
	@mkdir -p -- "$(BUILD_ROOT)/.modex"
	+flock --exclusive --close "$(UNIT_BUILD_LOCK)" $(MAKE) --no-print-directory test-run-internal

test-run-internal:
	+$(MAKE) --no-print-directory build-internal
	+$(MAKE) --no-print-directory --jobs=$(MODEX_UNIT_JOBS) unit-run-internal
	$(PYTHON) scripts/ci/run-unittest.py

ci-bootstrap:
	BWRAP_BIN="$$(scripts/ci/ensure-bwrap.sh)" && BWRAP="$$BWRAP_BIN" MODEX_TOOLCHAIN_DIR="$(MODEX_TOOLCHAIN_DIR)" PYTHON="$(PYTHON)" scripts/ci/bootstrap.sh --install-mojo

ci-fast:
	MODEX_TOOLCHAIN_DIR="$(MODEX_TOOLCHAIN_DIR)" PYTHON="$(PYTHON)" scripts/ci/run-fast.sh

ci-full:
	MODEX_TOOLCHAIN_DIR="$(MODEX_TOOLCHAIN_DIR)" PYTHON="$(PYTHON)" scripts/ci/run-full.sh

ci-parity:
	$(PYTHON) scripts/ci/check-parity-complete.py

ci-validate:
	scripts/ci/validate-workflows.sh

ci-dependencies:
	$(PYTHON) scripts/ci/check-product-dependencies.py
