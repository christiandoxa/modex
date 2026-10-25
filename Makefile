MOJO ?= mojo
MOJO_VERSION := Mojo 1.2.0 (2016d0cd)
MOJO_FLAGS := -O3 --target-cpu=x86-64-v3

.PHONY: build check-toolchain probes test unit

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
	$(MOJO) build $(MOJO_FLAGS) -I src probes/process_spawn.mojo -o build/probes/process_spawn
	build/probes/process_spawn
	$(MOJO) build $(MOJO_FLAGS) probes/socket.mojo -o build/probes/socket
	build/probes/socket

unit: check-toolchain
	mkdir -p build/tests
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_provider_sse_wire.mojo -o build/tests/test_provider_sse_wire
	build/tests/test_provider_sse_wire
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_provider_sse_json.mojo -o build/tests/test_provider_sse_json
	build/tests/test_provider_sse_json
	$(MOJO) build $(MOJO_FLAGS) -I src tests/provider_sse_driver.mojo -o build/tests/provider_sse_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_provider_chat_chunk.mojo -o build/tests/test_provider_chat_chunk
	build/tests/test_provider_chat_chunk
	$(MOJO) build $(MOJO_FLAGS) -I src tests/provider_chat_chunk_driver.mojo -o build/tests/provider_chat_chunk_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_provider_sse_events.mojo -o build/tests/test_provider_sse_events
	build/tests/test_provider_sse_events
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_provider_chat_usage.mojo -o build/tests/test_provider_chat_usage
	build/tests/test_provider_chat_usage
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_provider_chat_tools.mojo -o build/tests/test_provider_chat_tools
	build/tests/test_provider_chat_tools
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_uuid7.mojo -o build/tests/test_uuid7
	build/tests/test_uuid7
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_provider_chat_items.mojo -o build/tests/test_provider_chat_items
	build/tests/test_provider_chat_items
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_rtk_command.mojo -o build/tests/test_rtk_command
	build/tests/test_rtk_command
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_provider_chat_metadata.mojo -o build/tests/test_provider_chat_metadata
	build/tests/test_provider_chat_metadata
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_provider_chat_stream.mojo -o build/tests/test_provider_chat_stream
	build/tests/test_provider_chat_stream
	$(MOJO) build $(MOJO_FLAGS) -I src tests/provider_chat_stream_driver.mojo -o build/tests/provider_chat_stream_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_provider_request_messages.mojo -o build/tests/test_provider_request_messages
	build/tests/test_provider_request_messages
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_provider_request_prepare.mojo -o build/tests/test_provider_request_prepare
	build/tests/test_provider_request_prepare
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_provider_request_tools.mojo -o build/tests/test_provider_request_tools
	build/tests/test_provider_request_tools
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_provider_request_params.mojo -o build/tests/test_provider_request_params
	build/tests/test_provider_request_params
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_provider_request.mojo -o build/tests/test_provider_request
	build/tests/test_provider_request
	$(MOJO) build $(MOJO_FLAGS) -I src tests/provider_request_driver.mojo -o build/tests/provider_request_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_provider_deepseek_transport.mojo -o build/tests/test_provider_deepseek_transport
	build/tests/test_provider_deepseek_transport
	$(MOJO) build $(MOJO_FLAGS) -I src tests/provider_deepseek_transport_driver.mojo -o build/tests/provider_deepseek_transport_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_json.mojo -o build/tests/test_json
	build/tests/test_json
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_json_float.mojo -o build/tests/test_json_float
	build/tests/test_json_float
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_sha256.mojo -o build/tests/test_sha256
	build/tests/test_sha256
	$(MOJO) build $(MOJO_FLAGS) -I src tests/sha256_driver.mojo -o build/tests/sha256_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/loopback_http_driver.mojo -o build/tests/loopback_http_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/loopback_http_stream_driver.mojo -o build/tests/loopback_http_stream_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_sessions.mojo -o build/tests/test_sessions
	build/tests/test_sessions
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_local_time.mojo -o build/tests/test_local_time
	build/tests/test_local_time
	$(MOJO) build $(MOJO_FLAGS) -I src tests/json_driver.mojo -o build/tests/json_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_zstd.mojo -o build/tests/test_zstd
	build/tests/test_zstd
	$(MOJO) build $(MOJO_FLAGS) -I src tests/zstd_driver.mojo -o build/tests/zstd_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/text_driver.mojo -o build/tests/text_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/width_memory_driver.mojo -o build/tests/width_memory_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/log_text_driver.mojo -o build/tests/log_text_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/log_transcript_driver.mojo -o build/tests/log_transcript_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/log_payload_driver.mojo -o build/tests/log_payload_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/log_payload_render_driver.mojo -o build/tests/log_payload_render_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/unicode_properties_driver.mojo -o build/tests/unicode_properties_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_toml.mojo -o build/tests/test_toml
	build/tests/test_toml
	$(MOJO) build $(MOJO_FLAGS) -I src tests/toml_driver.mojo -o build/tests/toml_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_log_time.mojo -o build/tests/test_log_time
	build/tests/test_log_time
	$(MOJO) build $(MOJO_FLAGS) -I src tests/log_time_driver.mojo -o build/tests/log_time_driver
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_log_follow.mojo -o build/tests/test_log_follow
	build/tests/test_log_follow $(CURDIR)/build/tests/log-follow-files
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_log_follow_paths.mojo -o build/tests/test_log_follow_paths
	build/tests/test_log_follow_paths $(CURDIR)/build/tests/follow-paths
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_log_operational.mojo -o build/tests/test_log_operational
	build/tests/test_log_operational
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_log_transcript_events.mojo -o build/tests/test_log_transcript_events
	build/tests/test_log_transcript_events
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_log_sources.mojo -o build/tests/test_log_sources
	build/tests/test_log_sources
	$(MOJO) build $(MOJO_FLAGS) -I src tests/process_child.mojo -o build/tests/process_child
	$(MOJO) build $(MOJO_FLAGS) -I src tests/test_process_spawn.mojo -o build/tests/test_process_spawn
	build/tests/test_process_spawn $(CURDIR)/build/tests/process_child

test: build unit
	python3 -m unittest discover -s tests -p 'test_*.py' -v
