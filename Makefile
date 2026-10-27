MOJO ?= mojo
MOJO_VERSION := Mojo 1.2.0 (2016d0cd)
MOJO_FLAGS := -O3 --target-cpu=x86-64-v3
BUILD_DIR ?= build
BUILD_ROOT := $(abspath $(BUILD_DIR))
PYTHON ?= python3

.PHONY: build check-toolchain probes test unit ci-bootstrap ci-fast ci-full ci-parity ci-validate ci-dependencies

check-toolchain:
	@test "$$($(MOJO) --version)" = "$(MOJO_VERSION)" || { echo 'Pinned toolchain required: $(MOJO_VERSION)' >&2; exit 1; }

build: check-toolchain
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

unit: check-toolchain
	mkdir -p $(BUILD_ROOT)/tests
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_provider_sse_wire.mojo -o $(BUILD_ROOT)/tests/test_provider_sse_wire
	$(BUILD_ROOT)/tests/test_provider_sse_wire
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_provider_sse_json.mojo -o $(BUILD_ROOT)/tests/test_provider_sse_json
	$(BUILD_ROOT)/tests/test_provider_sse_json
	$(MOJO) build $(MOJO_FLAGS) -I src tests/provider_sse_driver.mojo -o $(BUILD_ROOT)/tests/provider_sse_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_provider_chat_chunk.mojo -o $(BUILD_ROOT)/tests/test_provider_chat_chunk
	$(BUILD_ROOT)/tests/test_provider_chat_chunk
	$(MOJO) build $(MOJO_FLAGS) -I src tests/provider_chat_chunk_driver.mojo -o $(BUILD_ROOT)/tests/provider_chat_chunk_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_provider_sse_events.mojo -o $(BUILD_ROOT)/tests/test_provider_sse_events
	$(BUILD_ROOT)/tests/test_provider_sse_events
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_provider_chat_usage.mojo -o $(BUILD_ROOT)/tests/test_provider_chat_usage
	$(BUILD_ROOT)/tests/test_provider_chat_usage
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_provider_chat_tools.mojo -o $(BUILD_ROOT)/tests/test_provider_chat_tools
	$(BUILD_ROOT)/tests/test_provider_chat_tools
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_uuid7.mojo -o $(BUILD_ROOT)/tests/test_uuid7
	$(BUILD_ROOT)/tests/test_uuid7
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_provider_chat_items.mojo -o $(BUILD_ROOT)/tests/test_provider_chat_items
	$(BUILD_ROOT)/tests/test_provider_chat_items
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_rtk_command.mojo -o $(BUILD_ROOT)/tests/test_rtk_command
	$(BUILD_ROOT)/tests/test_rtk_command
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_provider_chat_metadata.mojo -o $(BUILD_ROOT)/tests/test_provider_chat_metadata
	$(BUILD_ROOT)/tests/test_provider_chat_metadata
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_provider_chat_stream.mojo -o $(BUILD_ROOT)/tests/test_provider_chat_stream
	$(BUILD_ROOT)/tests/test_provider_chat_stream
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_provider_chat_reader.mojo -o $(BUILD_ROOT)/tests/test_provider_chat_reader
	$(BUILD_ROOT)/tests/test_provider_chat_reader
	$(MOJO) build $(MOJO_FLAGS) -I src tests/provider_chat_stream_driver.mojo -o $(BUILD_ROOT)/tests/provider_chat_stream_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_provider_request_messages.mojo -o $(BUILD_ROOT)/tests/test_provider_request_messages
	$(BUILD_ROOT)/tests/test_provider_request_messages
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_provider_request_prepare.mojo -o $(BUILD_ROOT)/tests/test_provider_request_prepare
	$(BUILD_ROOT)/tests/test_provider_request_prepare
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_provider_request_tools.mojo -o $(BUILD_ROOT)/tests/test_provider_request_tools
	$(BUILD_ROOT)/tests/test_provider_request_tools
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_provider_request_params.mojo -o $(BUILD_ROOT)/tests/test_provider_request_params
	$(BUILD_ROOT)/tests/test_provider_request_params
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_provider_request.mojo -o $(BUILD_ROOT)/tests/test_provider_request
	$(BUILD_ROOT)/tests/test_provider_request
	$(MOJO) build $(MOJO_FLAGS) -I src tests/provider_request_driver.mojo -o $(BUILD_ROOT)/tests/provider_request_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_provider_chat_buffered.mojo -o $(BUILD_ROOT)/tests/test_provider_chat_buffered
	$(BUILD_ROOT)/tests/test_provider_chat_buffered
	$(MOJO) build $(MOJO_FLAGS) -I src tests/provider_chat_buffered_driver.mojo -o $(BUILD_ROOT)/tests/provider_chat_buffered_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_provider_deepseek_transport.mojo -o $(BUILD_ROOT)/tests/test_provider_deepseek_transport
	$(BUILD_ROOT)/tests/test_provider_deepseek_transport
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_provider_rate_limits.mojo -o $(BUILD_ROOT)/tests/test_provider_rate_limits
	$(BUILD_ROOT)/tests/test_provider_rate_limits
	$(MOJO) build $(MOJO_FLAGS) -I src tests/provider_deepseek_transport_driver.mojo -o $(BUILD_ROOT)/tests/provider_deepseek_transport_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_provider_conversations.mojo -o $(BUILD_ROOT)/tests/test_provider_conversations
	$(BUILD_ROOT)/tests/test_provider_conversations
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_provider_passthrough.mojo -o $(BUILD_ROOT)/tests/test_provider_passthrough
	$(BUILD_ROOT)/tests/test_provider_passthrough
	$(MOJO) build $(MOJO_FLAGS) -I src tests/provider_passthrough_driver.mojo -o $(BUILD_ROOT)/tests/provider_passthrough_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_runtime_recovery.mojo -o $(BUILD_ROOT)/tests/test_runtime_recovery
	$(BUILD_ROOT)/tests/test_runtime_recovery
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_quota_handoff_04392.mojo -o $(BUILD_ROOT)/tests/test_quota_handoff_04392
	$(BUILD_ROOT)/tests/test_quota_handoff_04392
	$(MOJO) build $(MOJO_FLAGS) -I src tests/runtime_recovery_driver.mojo -o $(BUILD_ROOT)/tests/runtime_recovery_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_inspection_cli.mojo -o $(BUILD_ROOT)/tests/test_inspection_cli
	$(BUILD_ROOT)/tests/test_inspection_cli
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_gateway_cli.mojo -o $(BUILD_ROOT)/tests/test_gateway_cli
	$(BUILD_ROOT)/tests/test_gateway_cli
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_super_cli.mojo -o $(BUILD_ROOT)/tests/test_super_cli
	$(BUILD_ROOT)/tests/test_super_cli
	$(MOJO) build $(MOJO_FLAGS) -I src tests/local_rewrite_driver.mojo -o $(BUILD_ROOT)/tests/local_rewrite_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_json.mojo -o $(BUILD_ROOT)/tests/test_json
	$(BUILD_ROOT)/tests/test_json
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_json_float.mojo -o $(BUILD_ROOT)/tests/test_json_float
	$(BUILD_ROOT)/tests/test_json_float
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_sha256.mojo -o $(BUILD_ROOT)/tests/test_sha256
	$(BUILD_ROOT)/tests/test_sha256
	$(MOJO) build $(MOJO_FLAGS) -I src tests/sha256_driver.mojo -o $(BUILD_ROOT)/tests/sha256_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/loopback_http_driver.mojo -o $(BUILD_ROOT)/tests/loopback_http_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/loopback_http_stream_driver.mojo -o $(BUILD_ROOT)/tests/loopback_http_stream_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/loopback_server_driver.mojo -o $(BUILD_ROOT)/tests/loopback_server_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_sessions.mojo -o $(BUILD_ROOT)/tests/test_sessions
	$(BUILD_ROOT)/tests/test_sessions
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_session_cli.mojo -o $(BUILD_ROOT)/tests/test_session_cli
	$(BUILD_ROOT)/tests/test_session_cli
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_local_time.mojo -o $(BUILD_ROOT)/tests/test_local_time
	$(BUILD_ROOT)/tests/test_local_time
	$(MOJO) build $(MOJO_FLAGS) -I src tests/json_driver.mojo -o $(BUILD_ROOT)/tests/json_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_zstd.mojo -o $(BUILD_ROOT)/tests/test_zstd
	$(BUILD_ROOT)/tests/test_zstd
	$(MOJO) build $(MOJO_FLAGS) -I src tests/zstd_driver.mojo -o $(BUILD_ROOT)/tests/zstd_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/text_driver.mojo -o $(BUILD_ROOT)/tests/text_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/width_memory_driver.mojo -o $(BUILD_ROOT)/tests/width_memory_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/log_text_driver.mojo -o $(BUILD_ROOT)/tests/log_text_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/log_transcript_driver.mojo -o $(BUILD_ROOT)/tests/log_transcript_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/log_payload_driver.mojo -o $(BUILD_ROOT)/tests/log_payload_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/log_payload_render_driver.mojo -o $(BUILD_ROOT)/tests/log_payload_render_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/unicode_properties_driver.mojo -o $(BUILD_ROOT)/tests/unicode_properties_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_toml.mojo -o $(BUILD_ROOT)/tests/test_toml
	$(BUILD_ROOT)/tests/test_toml
	$(MOJO) build $(MOJO_FLAGS) -I src tests/toml_driver.mojo -o $(BUILD_ROOT)/tests/toml_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_log_time.mojo -o $(BUILD_ROOT)/tests/test_log_time
	$(BUILD_ROOT)/tests/test_log_time
	$(MOJO) build $(MOJO_FLAGS) -I src tests/log_time_driver.mojo -o $(BUILD_ROOT)/tests/log_time_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_log_follow.mojo -o $(BUILD_ROOT)/tests/test_log_follow
	$(BUILD_ROOT)/tests/test_log_follow $(BUILD_ROOT)/tests/log-follow-files
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_log_follow_paths.mojo -o $(BUILD_ROOT)/tests/test_log_follow_paths
	$(BUILD_ROOT)/tests/test_log_follow_paths $(BUILD_ROOT)/tests/follow-paths
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_log_operational.mojo -o $(BUILD_ROOT)/tests/test_log_operational
	$(BUILD_ROOT)/tests/test_log_operational
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_log_transcript_events.mojo -o $(BUILD_ROOT)/tests/test_log_transcript_events
	$(BUILD_ROOT)/tests/test_log_transcript_events
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_log_sources.mojo -o $(BUILD_ROOT)/tests/test_log_sources
	$(BUILD_ROOT)/tests/test_log_sources
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_app_server_args.mojo -o $(BUILD_ROOT)/tests/test_app_server_args
	$(BUILD_ROOT)/tests/test_app_server_args
	$(MOJO) build $(MOJO_FLAGS) -I src tests/app_server_args_driver.mojo -o $(BUILD_ROOT)/tests/app_server_args_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/app_server_rpc_driver.mojo -o $(BUILD_ROOT)/tests/app_server_rpc_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_app_server_rpc.mojo -o $(BUILD_ROOT)/tests/test_app_server_rpc
	$(BUILD_ROOT)/tests/test_app_server_rpc
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_super_hooks.mojo -o $(BUILD_ROOT)/tests/test_super_hooks
	$(BUILD_ROOT)/tests/test_super_hooks
	$(MOJO) build $(MOJO_FLAGS) -I src tests/super_hooks_driver.mojo -o $(BUILD_ROOT)/tests/super_hooks_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/process_wait_child.mojo -o $(BUILD_ROOT)/tests/process_wait_child
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_process_wait.mojo -o $(BUILD_ROOT)/tests/test_process_wait
	$(BUILD_ROOT)/tests/test_process_wait $(BUILD_ROOT)/tests/process_wait_child
	$(MOJO) build $(MOJO_FLAGS) -I src tests/process_stdio_child.mojo -o $(BUILD_ROOT)/tests/process_stdio_child
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_process_stdio.mojo -o $(BUILD_ROOT)/tests/test_process_stdio
	$(BUILD_ROOT)/tests/test_process_stdio $(BUILD_ROOT)/tests/process_stdio_child
	$(MOJO) build $(MOJO_FLAGS) -I src tests/process_capture_child.mojo -o $(BUILD_ROOT)/tests/process_capture_child
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_process_capture.mojo -o $(BUILD_ROOT)/tests/test_process_capture
	$(BUILD_ROOT)/tests/test_process_capture $(BUILD_ROOT)/tests/process_capture_child
	$(MOJO) build $(MOJO_FLAGS) -I src tests/process_child.mojo -o $(BUILD_ROOT)/tests/process_child
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_process_spawn.mojo -o $(BUILD_ROOT)/tests/test_process_spawn
	$(BUILD_ROOT)/tests/test_process_spawn $(BUILD_ROOT)/tests/process_child

test: build unit
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
