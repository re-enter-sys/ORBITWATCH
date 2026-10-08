"""
Tests for the OrbitWatch SDR-to-DSP receive pipeline.
"""

from __future__ import annotations

import math

import pytest

from groundstation.pipeline import (
    DemodulationMode,
    PipelineConfig,
    ReceiverPipeline,
)
from groundstation.sdr import (
    IQSampleBuffer,
    IQSampleFormat,
    ReceiverConfig,
    SDRReceiver,
)
from groundstation.signal import (
    FilterConfig,
    SignalFilter,
)


def make_iq_buffer(
    samples: tuple[complex, ...],
    sample_rate_hz: float = 8000.0,
    center_frequency_hz: float = 145_800_000.0,
) -> IQSampleBuffer:
    """Create a deterministic IQ buffer for testing."""

    return IQSampleBuffer.from_iterable(
        samples=samples,
        sample_rate_hz=sample_rate_hz,
        center_frequency_hz=center_frequency_hz,
        sample_format=IQSampleFormat.COMPLEX64,
    )


def make_receiver(
    samples: tuple[complex, ...],
    sample_rate_hz: float = 8000.0,
    center_frequency_hz: float = 145_800_000.0,
) -> SDRReceiver:
    """Create a receiver using a deterministic sample provider."""

    config = ReceiverConfig(
        center_frequency_hz=center_frequency_hz,
        sample_rate_hz=sample_rate_hz,
    )

    def provider(count: int):
        """Return deterministic replay samples."""

        if not samples:
            return ()

        repeats = (
            count + len(samples) - 1
        ) // len(samples)

        return (
            samples * repeats
        )[:count]

    return SDRReceiver(
        config=config,
        sample_provider=provider,
    )


def test_pipeline_config_defaults() -> None:
    config = PipelineConfig()

    assert config.demodulation_mode == DemodulationMode.FM
    assert config.remove_dc is True
    assert config.low_pass_enabled is True
    assert config.normalize_enabled is True
    assert config.filter_window_size == 5
    assert config.samples_per_symbol == 1.0


def test_pipeline_config_accepts_string_mode() -> None:
    config = PipelineConfig(
        demodulation_mode="AFSK"
    )

    assert (
        config.demodulation_mode
        == DemodulationMode.AFSK
    )


def test_pipeline_config_rejects_invalid_mode() -> None:
    with pytest.raises(ValueError):
        PipelineConfig(
            demodulation_mode="INVALID"
        )


def test_pipeline_config_rejects_invalid_filter_window() -> None:
    with pytest.raises(ValueError):
        PipelineConfig(
            filter_window_size=0
        )


def test_pipeline_config_rejects_invalid_normalization_peak() -> None:
    with pytest.raises(ValueError):
        PipelineConfig(
            normalization_peak=0
        )


def test_pipeline_config_rejects_invalid_samples_per_symbol() -> None:
    with pytest.raises(ValueError):
        PipelineConfig(
            samples_per_symbol=0
        )


def test_pipeline_config_rejects_negative_offset() -> None:
    with pytest.raises(ValueError):
        PipelineConfig(
            symbol_offset=-1
        )


def test_pipeline_config_rejects_equal_afsk_frequencies() -> None:
    with pytest.raises(ValueError):
        PipelineConfig(
            afsk_mark_frequency_hz=1200,
            afsk_space_frequency_hz=1200,
        )


def test_pipeline_config_serialization() -> None:
    config = PipelineConfig(
        demodulation_mode=DemodulationMode.GMSK,
        samples_per_symbol=4,
        symbol_offset=1,
    )

    data = config.to_dict()

    assert data["demodulation_mode"] == "GMSK"
    assert data["samples_per_symbol"] == 4
    assert data["symbol_offset"] == 1


def test_pipeline_requires_receiver() -> None:
    with pytest.raises(TypeError):
        ReceiverPipeline(None)  # type: ignore[arg-type]


def test_pipeline_initial_status() -> None:
    receiver = make_receiver((1 + 0j,))

    pipeline = ReceiverPipeline(receiver)

    status = pipeline.status()

    assert status.running is False
    assert status.processed_blocks == 0
    assert status.processed_samples == 0
    assert status.last_result_available is False


def test_pipeline_start_and_stop() -> None:
    receiver = make_receiver(
        (1 + 0j, 0.5 + 0.5j)
    )

    pipeline = ReceiverPipeline(receiver)

    pipeline.start()

    assert pipeline.is_running is True

    pipeline.stop()

    assert pipeline.is_running is False


def test_pipeline_processes_iq_buffer() -> None:
    samples = tuple(
        complex(
            math.cos(index * 0.2),
            math.sin(index * 0.2),
        )
        for index in range(32)
    )

    receiver = make_receiver(samples)

    pipeline = ReceiverPipeline(
        receiver,
        PipelineConfig(
            samples_per_symbol=2,
        ),
    )

    result = pipeline.process(
        make_iq_buffer(samples)
    )

    assert result.input_sample_count == 32
    assert result.filtered_sample_count == 32
    assert result.demodulated_sample_count == 32
    assert result.synchronized_sample_count > 0
    assert result.symbol_count > 0
    assert result.demodulation_mode == DemodulationMode.FM


def test_pipeline_capture_and_process() -> None:
    samples = (
        1 + 0j,
        0.8 + 0.2j,
        0.5 + 0.5j,
        0.2 + 0.8j,
    )

    receiver = make_receiver(samples)

    pipeline = ReceiverPipeline(receiver)

    pipeline.start()

    result = pipeline.capture_and_process(16)

    assert result.input_sample_count == 16
    assert result.demodulated_sample_count == 16

    pipeline.stop()


def test_pipeline_capture_requires_running_receiver() -> None:
    receiver = make_receiver(
        (1 + 0j,)
    )

    pipeline = ReceiverPipeline(receiver)

    with pytest.raises(RuntimeError):
        pipeline.capture_and_process(8)


def test_pipeline_capture_rejects_invalid_count() -> None:
    receiver = make_receiver(
        (1 + 0j,)
    )

    pipeline = ReceiverPipeline(receiver)

    pipeline.start()

    with pytest.raises(ValueError):
        pipeline.capture_and_process(0)

    pipeline.stop()


@pytest.mark.parametrize(
    "mode",
    [
        DemodulationMode.FM,
        DemodulationMode.AFSK,
        DemodulationMode.GMSK,
    ],
)
def test_pipeline_supports_all_demodulation_modes(
    mode: DemodulationMode,
) -> None:
    samples = tuple(
        complex(
            math.cos(index * 0.1),
            math.sin(index * 0.1),
        )
        for index in range(40)
    )

    receiver = make_receiver(samples)

    pipeline = ReceiverPipeline(
        receiver,
        PipelineConfig(
            demodulation_mode=mode,
            samples_per_symbol=2,
        ),
    )

    result = pipeline.process(
        make_iq_buffer(samples)
    )

    assert result.demodulation_mode == mode
    assert result.demodulated_sample_count == 40
    assert len(result.binary_symbols) > 0


def test_pipeline_can_disable_filtering() -> None:
    samples = (
        1 + 1j,
        2 + 2j,
        3 + 3j,
        4 + 4j,
    )

    receiver = make_receiver(samples)

    pipeline = ReceiverPipeline(
        receiver,
        PipelineConfig(
            remove_dc=False,
            low_pass_enabled=False,
            normalize_enabled=False,
        ),
    )

    result = pipeline.process(
        make_iq_buffer(samples)
    )

    assert result.filtered_samples == samples


def test_pipeline_normalization_limits_peak() -> None:
    samples = (
        2 + 0j,
        0 + 4j,
        -3 + 0j,
    )

    receiver = make_receiver(samples)

    pipeline = ReceiverPipeline(
        receiver,
        PipelineConfig(
            remove_dc=False,
            low_pass_enabled=False,
            normalize_enabled=True,
            normalization_peak=1.0,
        ),
    )

    result = pipeline.process(
        make_iq_buffer(samples)
    )

    assert max(
        abs(sample)
        for sample in result.filtered_samples
    ) == pytest.approx(1.0)


def test_pipeline_binary_symbols_are_binary() -> None:
    samples = tuple(
        complex(
            math.cos(index * 0.3),
            math.sin(index * 0.3),
        )
        for index in range(50)
    )

    receiver = make_receiver(samples)

    pipeline = ReceiverPipeline(
        receiver,
        PipelineConfig(
            samples_per_symbol=2,
        ),
    )

    result = pipeline.process(
        make_iq_buffer(samples)
    )

    assert set(result.binary_symbols).issubset(
        {0, 1}
    )


def test_pipeline_result_metadata() -> None:
    samples = (
        1 + 0j,
        0 + 1j,
        -1 + 0j,
        0 - 1j,
    )

    receiver = make_receiver(samples)

    pipeline = ReceiverPipeline(receiver)

    result = pipeline.process(
        make_iq_buffer(samples)
    )

    assert result.metadata["source"] == "iq_buffer"
    assert (
        result.metadata["demodulator_mode"]
        == "FM"
    )
    assert (
        result.metadata["sample_format"]
        == IQSampleFormat.COMPLEX64.value
    )


def test_pipeline_result_serialization() -> None:
    samples = (
        1 + 0j,
        0 + 1j,
        -1 + 0j,
        0 - 1j,
    )

    receiver = make_receiver(samples)

    pipeline = ReceiverPipeline(receiver)

    result = pipeline.process(
        make_iq_buffer(samples)
    )

    data = result.to_dict()

    assert data["input_sample_count"] == 4
    assert data["filtered_sample_count"] == 4
    assert data["demodulated_sample_count"] == 4
    assert data["demodulation_mode"] == "FM"
    assert "duration_seconds" in data
    assert "binary_symbols" in data


def test_pipeline_duration() -> None:
    samples = tuple(
        1 + 0j
        for _ in range(100)
    )

    receiver = make_receiver(
        samples,
        sample_rate_hz=1000.0,
    )

    pipeline = ReceiverPipeline(receiver)

    result = pipeline.process(
        make_iq_buffer(
            samples,
            sample_rate_hz=1000.0,
        )
    )

    assert result.duration_seconds == pytest.approx(
        0.1
    )


def test_pipeline_peak_is_non_negative() -> None:
    samples = tuple(
        complex(
            math.cos(index),
            math.sin(index),
        )
        for index in range(20)
    )

    receiver = make_receiver(samples)

    pipeline = ReceiverPipeline(receiver)

    result = pipeline.process(
        make_iq_buffer(samples)
    )

    assert result.peak >= 0.0


def test_pipeline_has_signal_for_processed_samples() -> None:
    samples = (
        1 + 0j,
        0.5 + 0.5j,
        0 + 1j,
    )

    receiver = make_receiver(samples)

    pipeline = ReceiverPipeline(receiver)

    result = pipeline.process(
        make_iq_buffer(samples)
    )

    assert result.has_signal is True


def test_pipeline_statistics() -> None:
    samples = (
        1 + 0j,
        0 + 1j,
        -1 + 0j,
        0 - 1j,
    )

    receiver = make_receiver(samples)

    pipeline = ReceiverPipeline(receiver)

    pipeline.process(
        make_iq_buffer(samples)
    )

    pipeline.process(
        make_iq_buffer(samples)
    )

    status = pipeline.status()

    assert status.processed_blocks == 2
    assert status.processed_samples == 8
    assert status.last_result_available is True


def test_pipeline_reset_statistics() -> None:
    samples = (
        1 + 0j,
        0 + 1j,
    )

    receiver = make_receiver(samples)

    pipeline = ReceiverPipeline(receiver)

    pipeline.process(
        make_iq_buffer(samples)
    )

    pipeline.reset_statistics()

    status = pipeline.status()

    assert status.processed_blocks == 0
    assert status.processed_samples == 0
    assert status.last_result_available is False
    assert pipeline.last_result is None


def test_pipeline_filter_stage_uses_configured_window() -> None:
    samples = (
        1 + 0j,
        2 + 0j,
        3 + 0j,
        4 + 0j,
    )

    receiver = make_receiver(samples)

    pipeline = ReceiverPipeline(
        receiver,
        PipelineConfig(
            filter_window_size=2,
            remove_dc=False,
            low_pass_enabled=True,
            normalize_enabled=False,
        ),
    )

    result = pipeline.process(
        make_iq_buffer(samples)
    )

    assert result.filtered_samples == (
        1 + 0j,
        1.5 + 0j,
        2.5 + 0j,
        3.5 + 0j,
    )


def test_pipeline_symbol_offset() -> None:
    samples = tuple(
        complex(
            math.cos(index * 0.1),
            math.sin(index * 0.1),
        )
        for index in range(20)
    )

    receiver = make_receiver(samples)

    pipeline = ReceiverPipeline(
        receiver,
        PipelineConfig(
            samples_per_symbol=2,
            symbol_offset=1,
        ),
    )

    result = pipeline.process(
        make_iq_buffer(samples)
    )

    assert result.synchronized_sample_count > 0
    assert result.symbol_count > 0


def test_pipeline_rejects_invalid_iq_buffer() -> None:
    receiver = make_receiver(
        (1 + 0j,)
    )

    pipeline = ReceiverPipeline(receiver)

    with pytest.raises(TypeError):
        pipeline.process(None)  # type: ignore[arg-type]


def test_pipeline_start_stop_multiple_times() -> None:
    receiver = make_receiver(
        (1 + 0j,)
    )

    pipeline = ReceiverPipeline(receiver)

    pipeline.start()
    assert pipeline.is_running is True

    pipeline.stop()
    assert pipeline.is_running is False

    pipeline.start()
    assert pipeline.is_running is True

    pipeline.stop()
    assert pipeline.is_running is False
