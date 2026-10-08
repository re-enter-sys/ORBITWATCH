"""
Tests for the OrbitWatch signal-processing subsystem.
"""

from __future__ import annotations

import math

import pytest

from groundstation.signal import (
    AFSKDemodulator,
    DemodulatedSignal,
    FMDemodulator,
    FilterConfig,
    GMSKDemodulator,
    SignalFilter,
    SymbolSynchronizer,
    normalize_signal,
)


def test_filter_config_defaults() -> None:
    config = FilterConfig()

    assert config.window_size == 5


def test_filter_config_rejects_invalid_window() -> None:
    with pytest.raises(ValueError):
        FilterConfig(window_size=0)

    with pytest.raises(ValueError):
        FilterConfig(window_size=-1)


def test_low_pass_filter() -> None:
    signal = (
        1 + 0j,
        2 + 0j,
        3 + 0j,
        4 + 0j,
        5 + 0j,
    )

    result = SignalFilter(
        FilterConfig(window_size=3)
    ).low_pass(signal)

    assert len(result) == 5
    assert result[0] == pytest.approx(1 + 0j)
    assert result[1] == pytest.approx(1.5 + 0j)
    assert result[2] == pytest.approx(2 + 0j)


def test_low_pass_empty_signal() -> None:
    result = SignalFilter().low_pass([])

    assert result == ()


def test_low_pass_rejects_non_complex_samples() -> None:
    with pytest.raises(TypeError):
        SignalFilter().low_pass(
            [1, 2, 3]  # type: ignore[list-item]
        )


def test_high_pass_filter() -> None:
    signal = (
        1 + 0j,
        2 + 0j,
        3 + 0j,
        4 + 0j,
        5 + 0j,
    )

    result = SignalFilter(
        FilterConfig(window_size=3)
    ).high_pass(signal)

    assert len(result) == 5
    assert result[0] == pytest.approx(0 + 0j)
    assert result[1] == pytest.approx(0.5 + 0j)
    assert result[2] == pytest.approx(1 + 0j)


def test_remove_dc() -> None:
    signal = (
        3 + 1j,
        5 + 1j,
        7 + 1j,
    )

    result = SignalFilter().remove_dc(signal)

    assert result[0] == pytest.approx(-2 + 0j)
    assert result[1] == pytest.approx(0 + 0j)
    assert result[2] == pytest.approx(2 + 0j)


def test_remove_dc_empty_signal() -> None:
    assert SignalFilter().remove_dc([]) == ()


def test_smooth_magnitude() -> None:
    signal = (
        1 + 0j,
        3 + 0j,
        5 + 0j,
    )

    result = SignalFilter(
        FilterConfig(window_size=3)
    ).smooth_magnitude(signal)

    assert result[0] == pytest.approx(1.0)
    assert result[1] == pytest.approx(2.0)
    assert result[2] == pytest.approx(3.0)


def test_smooth_magnitude_empty() -> None:
    assert SignalFilter().smooth_magnitude([]) == ()


def test_normalize_signal() -> None:
    signal = (
        1 + 0j,
        2 + 0j,
        -4 + 0j,
    )

    result = normalize_signal(signal)

    assert max(
        abs(sample)
        for sample in result
    ) == pytest.approx(1.0)

    assert result == pytest.approx(
        (
            0.25 + 0j,
            0.5 + 0j,
            -1 + 0j,
        )
    )


def test_normalize_signal_custom_peak() -> None:
    signal = (
        1 + 0j,
        2 + 0j,
    )

    result = normalize_signal(
        signal,
        peak=2.0,
    )

    assert result == pytest.approx(
        (
            1 + 0j,
            2 + 0j,
        )
    )


def test_normalize_signal_empty() -> None:
    assert normalize_signal([]) == ()


def test_normalize_signal_all_zero() -> None:
    signal = (
        0 + 0j,
        0 + 0j,
        0 + 0j,
    )

    result = normalize_signal(signal)

    assert result == (
        0 + 0j,
        0 + 0j,
        0 + 0j,
    )


def test_normalize_signal_rejects_invalid_peak() -> None:
    with pytest.raises(ValueError):
        normalize_signal(
            [1 + 0j],
            peak=0,
        )

    with pytest.raises(ValueError):
        normalize_signal(
            [1 + 0j],
            peak=-1,
        )


def test_normalize_signal_accepts_numeric_samples() -> None:
    result = normalize_signal(
        [1, 2, 3],
    )

    assert result == pytest.approx(
        (
            1 / 3,
            2 / 3,
            1.0,
        )
    )


def test_demodulated_signal() -> None:
    signal = DemodulatedSignal(
        samples=(0.0, 0.5, -0.5, 1.0),
        sample_rate_hz=1000.0,
        mode="TEST",
    )

    assert signal.count == 4
    assert signal.duration_seconds == pytest.approx(0.004)
    assert signal.peak == pytest.approx(1.0)


def test_demodulated_signal_peak_empty() -> None:
    signal = DemodulatedSignal(
        samples=(),
        sample_rate_hz=1000.0,
        mode="TEST",
    )

    assert signal.count == 0
    assert signal.duration_seconds == 0.0
    assert signal.peak == 0.0


def test_fm_demodulator_mode() -> None:
    demodulator = FMDemodulator()

    assert demodulator.mode == "FM"


def test_fm_demodulator() -> None:
    samples = (
        1 + 0j,
        1 + 1j,
        0 + 1j,
        -1 + 1j,
    )

    result = FMDemodulator().demodulate(
        samples,
        sample_rate_hz=1000.0,
    )

    assert isinstance(
        result,
        DemodulatedSignal,
    )

    assert result.mode == "FM"
    assert result.count == 4
    assert result.samples[0] == pytest.approx(0.0)

    assert result.samples[1] == pytest.approx(
        math.pi / 4
    )

    assert result.samples[2] == pytest.approx(
        math.pi / 4
    )

    assert result.samples[3] == pytest.approx(
        math.pi / 4
    )


def test_fm_demodulator_rejects_invalid_sample_rate() -> None:
    with pytest.raises(ValueError):
        FMDemodulator().demodulate(
            [1 + 0j],
            sample_rate_hz=0,
        )


def test_fm_demodulator_empty() -> None:
    result = FMDemodulator().demodulate(
        [],
        sample_rate_hz=1000.0,
    )

    assert result.samples == ()
    assert result.count == 0


def test_afsk_demodulator_defaults() -> None:
    demodulator = AFSKDemodulator()

    assert demodulator.mark_frequency_hz == 1200.0
    assert demodulator.space_frequency_hz == 2200.0
    assert demodulator.mode == "AFSK"


def test_afsk_demodulator_custom_frequencies() -> None:
    demodulator = AFSKDemodulator(
        mark_frequency_hz=1000.0,
        space_frequency_hz=2000.0,
    )

    assert demodulator.mark_frequency_hz == 1000.0
    assert demodulator.space_frequency_hz == 2000.0


def test_afsk_rejects_invalid_frequencies() -> None:
    with pytest.raises(ValueError):
        AFSKDemodulator(
            mark_frequency_hz=0,
            space_frequency_hz=2200,
        )

    with pytest.raises(ValueError):
        AFSKDemodulator(
            mark_frequency_hz=1200,
            space_frequency_hz=0,
        )

    with pytest.raises(ValueError):
        AFSKDemodulator(
            mark_frequency_hz=1200,
            space_frequency_hz=1200,
        )


def test_afsk_demodulation() -> None:
    samples = (
        1 + 0j,
        1 + 1j,
        0 + 1j,
    )

    result = AFSKDemodulator().demodulate(
        samples,
        sample_rate_hz=1000.0,
    )

    assert result.mode == "AFSK"
    assert result.count == 3
    assert result.samples[0] == pytest.approx(0.0)


def test_gmsk_demodulator() -> None:
    samples = (
        1 + 0j,
        1 + 1j,
        0 + 1j,
    )

    result = GMSKDemodulator().demodulate(
        samples,
        sample_rate_hz=1000.0,
    )

    assert result.mode == "GMSK"
    assert result.count == 3
    assert result.samples[0] == pytest.approx(0.0)


def test_symbol_synchronizer_creation() -> None:
    synchronizer = SymbolSynchronizer(
        samples_per_symbol=4.0
    )

    assert synchronizer.samples_per_symbol == 4.0


def test_symbol_synchronizer_rejects_invalid_sps() -> None:
    with pytest.raises(ValueError):
        SymbolSynchronizer(
            samples_per_symbol=0
        )

    with pytest.raises(ValueError):
        SymbolSynchronizer(
            samples_per_symbol=-1
        )


def test_symbol_synchronizer() -> None:
    samples = (
        0.0,
        0.1,
        1.0,
        1.1,
        2.0,
        2.1,
        3.0,
        3.1,
    )

    result = SymbolSynchronizer(
        samples_per_symbol=2.0
    ).synchronize(samples)

    assert result.offset == 0
    assert result.samples_per_symbol == 2.0
    assert result.samples == pytest.approx(
        (
            0.0,
            1.0,
            2.0,
            3.0,
        )
    )
    assert result.symbol_count == 2


def test_symbol_synchronizer_with_offset() -> None:
    samples = (
        99.0,
        0.0,
        1.0,
        2.0,
        3.0,
    )

    result = SymbolSynchronizer(
        samples_per_symbol=1.0
    ).synchronize(
        samples,
        offset=1,
    )

    assert result.offset == 1
    assert result.samples == pytest.approx(
        (
            0.0,
            1.0,
            2.0,
            3.0,
        )
    )


def test_symbol_synchronizer_fractional_sps() -> None:
    samples = tuple(
        float(index)
        for index in range(10)
    )

    result = SymbolSynchronizer(
        samples_per_symbol=2.5
    ).synchronize(samples)

    assert result.samples == pytest.approx(
        (
            0.0,
            2.0,
            5.0,
            8.0,
        )
    )


def test_symbol_synchronizer_invalid_offset() -> None:
    synchronizer = SymbolSynchronizer(
        samples_per_symbol=2.0
    )

    with pytest.raises(ValueError):
        synchronizer.synchronize(
            [0.0, 1.0, 2.0],
            offset=-1,
        )

    with pytest.raises(ValueError):
        synchronizer.synchronize(
            [0.0, 1.0, 2.0],
            offset=3,
        )


def test_symbol_synchronizer_empty() -> None:
    result = SymbolSynchronizer(
        samples_per_symbol=2.0
    ).synchronize([])

    assert result.samples == ()
    assert result.symbol_count == 0


def test_recover_binary() -> None:
    samples = (
        -1.0,
        1.0,
        -0.5,
        0.5,
        2.0,
    )

    result = SymbolSynchronizer(
        samples_per_symbol=1.0
    ).recover_binary(
        samples,
        threshold=0.0,
    )

    assert result == (
        0,
        1,
        0,
        1,
        1,
    )


def test_recover_binary_custom_threshold() -> None:
    samples = (
        0.0,
        0.5,
        1.0,
        1.5,
    )

    result = SymbolSynchronizer(
        samples_per_symbol=1.0
    ).recover_binary(
        samples,
        threshold=1.0,
    )

    assert result == (
        0,
        0,
        1,
        1,
    )
