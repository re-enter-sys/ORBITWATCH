"""
Tests for the OrbitWatch SDR subsystem.
"""

from __future__ import annotations

import pytest

from groundstation.sdr import (
    IQSampleBuffer,
    IQSampleFormat,
    ReceiverConfig,
    ReceiverState,
    SDRDevice,
    SDRDeviceManager,
    SDRDeviceState,
    SDRReceiver,
    interleaved_iq_to_complex,
    complex_to_interleaved_iq,
    normalize_device_index,
)


def test_sdr_device_creation() -> None:
    device = SDRDevice(
        index=0,
        name="RTL-SDR Blog V4",
        driver="rtl-sdr",
        serial="ABC123",
        state=SDRDeviceState.AVAILABLE,
    )

    assert device.index == 0
    assert device.name == "RTL-SDR Blog V4"
    assert device.driver == "rtl-sdr"
    assert device.serial == "ABC123"
    assert device.state == SDRDeviceState.AVAILABLE


def test_sdr_device_identifier_with_serial() -> None:
    device = SDRDevice(
        index=0,
        name="RTL-SDR",
        driver="rtl-sdr",
        serial="ABC123",
    )

    assert device.identifier == "RTL-SDR (ABC123)"


def test_sdr_device_identifier_without_serial() -> None:
    device = SDRDevice(
        index=2,
        name="RTL-SDR",
        driver="rtl-sdr",
    )

    assert device.identifier == "RTL-SDR [2]"


def test_parse_rtl_test_output() -> None:
    output = """
Found 2 device(s):
  0: RTLSDRBlog, Blog V4, SN: ABC123
  1: Generic RTL2832U OEM
"""

    devices = SDRDeviceManager._discover_with_rtl_test

    # Test the parser through the module-level implementation
    # without requiring physical SDR hardware.
    from groundstation.sdr.device import _parse_rtl_test_output

    parsed = _parse_rtl_test_output(output)

    assert len(parsed) == 2
    assert parsed[0].index == 0
    assert parsed[1].index == 1
    assert parsed[0].driver == "rtl-sdr"
    assert parsed[0].state == SDRDeviceState.AVAILABLE


def test_parse_rtl_test_output_ignores_invalid_lines() -> None:
    from groundstation.sdr.device import _parse_rtl_test_output

    output = """
No devices found.
Device #invalid: broken
Device #2: Test SDR
"""

    devices = _parse_rtl_test_output(output)

    assert len(devices) == 1
    assert devices[0].index == 2
    assert devices[0].name == "Test SDR"


def test_device_manager_initial_state() -> None:
    manager = SDRDeviceManager()

    assert manager.devices == ()


def test_device_manager_get_missing_device() -> None:
    manager = SDRDeviceManager()

    assert manager.get_device(0) is None


def test_normalize_device_index() -> None:
    devices = [
        SDRDevice(
            index=0,
            name="SDR-0",
            driver="test",
        ),
        SDRDevice(
            index=1,
            name="SDR-1",
            driver="test",
        ),
    ]

    selected = normalize_device_index(
        1,
        devices,
    )

    assert selected.name == "SDR-1"


def test_normalize_device_index_invalid() -> None:
    devices = [
        SDRDevice(
            index=0,
            name="SDR-0",
            driver="test",
        )
    ]

    with pytest.raises(ValueError):
        normalize_device_index(
            99,
            devices,
        )


def test_iq_sample_buffer_creation() -> None:
    buffer = IQSampleBuffer.from_iterable(
        samples=[
            1 + 2j,
            2 + 3j,
            3 + 4j,
        ],
        sample_rate_hz=2_000_000,
        center_frequency_hz=145_800_000,
    )

    assert buffer.count == 3
    assert len(buffer) == 3
    assert buffer.sample_rate_hz == 2_000_000
    assert buffer.center_frequency_hz == 145_800_000
    assert buffer.format == IQSampleFormat.COMPLEX64


def test_iq_sample_buffer_iteration_and_indexing() -> None:
    buffer = IQSampleBuffer.from_iterable(
        samples=[
            1 + 0j,
            2 + 0j,
            3 + 0j,
        ],
        sample_rate_hz=1_000,
        center_frequency_hz=100_000,
    )

    assert list(buffer) == [
        1 + 0j,
        2 + 0j,
        3 + 0j,
    ]

    assert buffer[1] == 2 + 0j


def test_iq_sample_buffer_duration() -> None:
    buffer = IQSampleBuffer.from_iterable(
        samples=[1 + 0j] * 1000,
        sample_rate_hz=1000,
        center_frequency_hz=100_000,
    )

    assert buffer.duration_seconds == pytest.approx(1.0)


def test_iq_sample_buffer_power_and_rms() -> None:
    buffer = IQSampleBuffer.from_iterable(
        samples=[
            1 + 0j,
            1 + 0j,
            1 + 0j,
            1 + 0j,
        ],
        sample_rate_hz=1000,
        center_frequency_hz=100_000,
    )

    assert buffer.mean_power == pytest.approx(1.0)
    assert buffer.rms_amplitude == pytest.approx(1.0)
    assert buffer.peak_amplitude() == pytest.approx(1.0)


def test_iq_empty_buffer_statistics() -> None:
    buffer = IQSampleBuffer.from_iterable(
        samples=[],
        sample_rate_hz=1000,
        center_frequency_hz=100_000,
    )

    assert buffer.count == 0
    assert buffer.duration_seconds == 0.0
    assert buffer.mean_power == 0.0
    assert buffer.rms_amplitude == 0.0
    assert buffer.peak_amplitude() == 0.0


def test_iq_rejects_invalid_sample_rate() -> None:
    with pytest.raises(ValueError):
        IQSampleBuffer.from_iterable(
            samples=[1 + 0j],
            sample_rate_hz=0,
            center_frequency_hz=100_000,
        )


def test_iq_rejects_non_complex_samples() -> None:
    with pytest.raises(TypeError):
        IQSampleBuffer.from_iterable(
            samples=[1],  # type: ignore[list-item]
            sample_rate_hz=1000,
            center_frequency_hz=100_000,
        )


def test_iq_rejects_non_finite_samples() -> None:
    with pytest.raises(ValueError):
        IQSampleBuffer.from_iterable(
            samples=[complex(float("nan"), 0.0)],
            sample_rate_hz=1000,
            center_frequency_hz=100_000,
        )


def test_interleaved_iq_conversion() -> None:
    result = interleaved_iq_to_complex(
        [
            1.0,
            2.0,
            3.0,
            4.0,
        ]
    )

    assert result == (
        1 + 2j,
        3 + 4j,
    )


def test_interleaved_iq_rejects_odd_length() -> None:
    with pytest.raises(ValueError):
        interleaved_iq_to_complex(
            [
                1.0,
                2.0,
                3.0,
            ]
        )


def test_complex_to_interleaved_iq() -> None:
    result = complex_to_interleaved_iq(
        [
            1 + 2j,
            3 + 4j,
        ]
    )

    assert result == (
        1.0,
        2.0,
        3.0,
        4.0,
    )


def test_complex_to_interleaved_iq_rejects_non_complex() -> None:
    with pytest.raises(TypeError):
        complex_to_interleaved_iq(
            [1],  # type: ignore[list-item]
        )


def test_receiver_config_defaults() -> None:
    config = ReceiverConfig()

    assert config.center_frequency_hz == 145_800_000.0
    assert config.sample_rate_hz == 2_048_000.0
    assert config.gain == "auto"
    assert config.ppm_correction == 0
    assert config.device_index == 0


def test_receiver_config_validation() -> None:
    with pytest.raises(ValueError):
        ReceiverConfig(
            center_frequency_hz=0,
        ).validate()

    with pytest.raises(ValueError):
        ReceiverConfig(
            sample_rate_hz=0,
        ).validate()

    with pytest.raises(TypeError):
        ReceiverConfig(
            ppm_correction="0",  # type: ignore[arg-type]
        ).validate()

    with pytest.raises(ValueError):
        ReceiverConfig(
            device_index=-1,
        ).validate()


def test_receiver_initial_state() -> None:
    receiver = SDRReceiver()

    assert receiver.state == ReceiverState.IDLE
    assert not receiver.is_receiving
    assert receiver.device is None
    assert receiver.uptime_seconds == 0.0


def test_receiver_replay_mode_start() -> None:
    def provider(count: int):
        return [1 + 0j] * count

    receiver = SDRReceiver(
        sample_provider=provider,
    )

    receiver.start()

    assert receiver.state == ReceiverState.RECEIVING
    assert receiver.is_receiving
    assert receiver.uptime_seconds >= 0.0


def test_receiver_capture_from_provider() -> None:
    def provider(count: int):
        return [complex(index, 0) for index in range(count)]

    receiver = SDRReceiver(
        sample_provider=provider,
    )

    receiver.start()

    buffer = receiver.capture(5)

    assert buffer.count == 5
    assert buffer.samples == (
        0 + 0j,
        1 + 0j,
        2 + 0j,
        3 + 0j,
        4 + 0j,
    )


def test_receiver_capture_limits_provider_output() -> None:
    def provider(count: int):
        return [1 + 0j] * (count + 10)

    receiver = SDRReceiver(
        sample_provider=provider,
    )

    receiver.start()

    buffer = receiver.capture(4)

    assert buffer.count == 4


def test_receiver_capture_requires_positive_count() -> None:
    def provider(count: int):
        return [1 + 0j] * count

    receiver = SDRReceiver(
        sample_provider=provider,
    )

    receiver.start()

    with pytest.raises(ValueError):
        receiver.capture(0)

    with pytest.raises(ValueError):
        receiver.capture(-1)


def test_receiver_capture_requires_running_state() -> None:
    receiver = SDRReceiver(
        sample_provider=lambda count: [1 + 0j] * count,
    )

    with pytest.raises(RuntimeError):
        receiver.capture(10)


def test_receiver_without_provider_requires_backend() -> None:
    receiver = SDRReceiver()

    receiver.state = ReceiverState.READY

    with pytest.raises(RuntimeError):
        receiver.capture(10)


def test_receiver_stop() -> None:
    receiver = SDRReceiver(
        sample_provider=lambda count: [1 + 0j] * count,
    )

    receiver.start()

    assert receiver.is_receiving

    receiver.stop()

    assert receiver.state == ReceiverState.STOPPED
    assert not receiver.is_receiving
    assert receiver.uptime_seconds == 0.0


def test_receiver_start_is_idempotent() -> None:
    receiver = SDRReceiver(
        sample_provider=lambda count: [1 + 0j] * count,
    )

    receiver.start()
    first_started_state = receiver.state

    receiver.start()

    assert first_started_state == ReceiverState.RECEIVING
    assert receiver.state == ReceiverState.RECEIVING


def test_receiver_reconfigure_when_stopped() -> None:
    receiver = SDRReceiver(
        sample_provider=lambda count: [1 + 0j] * count,
    )

    new_config = ReceiverConfig(
        center_frequency_hz=437_500_000.0,
        sample_rate_hz=1_000_000.0,
        gain="20",
        ppm_correction=2,
        device_index=1,
    )

    receiver.reconfigure(new_config)

    assert receiver.config == new_config
    assert receiver.device is None
    assert receiver.state == ReceiverState.IDLE


def test_receiver_reconfigure_while_receiving_fails() -> None:
    receiver = SDRReceiver(
        sample_provider=lambda count: [1 + 0j] * count,
    )

    receiver.start()

    with pytest.raises(RuntimeError):
        receiver.reconfigure(
            ReceiverConfig(
                center_frequency_hz=437_500_000.0,
            )
        )


def test_receiver_status() -> None:
    receiver = SDRReceiver(
        sample_provider=lambda count: [1 + 0j] * count,
    )

    status = receiver.status()

    assert status["state"] == "idle"
    assert status["device"] is None
    assert status["center_frequency_hz"] == 145_800_000.0
    assert status["sample_rate_hz"] == 2_048_000.0
    assert status["gain"] == "auto"
    assert status["ppm_correction"] == 0
    assert status["device_index"] == 0
    assert status["receiving"] is False
    assert status["uptime_seconds"] == 0.0
