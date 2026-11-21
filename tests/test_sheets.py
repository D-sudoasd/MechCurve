import matplotlib.pyplot as plt
import numpy as np

from mechcurve.sheets import strain_response


def test_strain_response_keeps_measured_repetitions_and_signed_residual():
    def cycle(n, applied, residual, status="complete"):
        return dict(
            cycle=n,
            status=status,
            total_strain_pp=applied,
            recoverable_pp=applied - residual,
            residual_segment_pp=residual,
        )

    records = [
        {"cycles": [cycle(1, 0.425, -0.008), cycle(8, 1.75, 0.016)]},
        {
            "cycles": [
                cycle(9, 1.75, 0.017),
                cycle(10, 2.2, 0.096),
                cycle(11, 0.1, 0, "partial_loading"),
            ]
        },
    ]
    fig = plt.figure()
    try:
        strain_response(fig, records)
        main, zoom = fig.axes
        for ax in (main, zoom):
            assert any(
                np.array_equal(line.get_ydata(), [0.03, 0.03]) for line in ax.lines
            )
        recover = np.vstack(
            [a.get_offsets() for a in main.collections if a.get_label() == "可恢复应变"]
        )
        residual = np.vstack(
            [
                a.get_offsets()
                for a in main.collections
                if a.get_label() == "段内残余应变"
            ]
        )
        np.testing.assert_allclose(
            recover, [[0.425, 0.433], [1.75, 1.734], [1.75, 1.733], [2.2, 2.104]]
        )
        np.testing.assert_allclose(residual[:, 1], [-0.008, 0.016, 0.017, 0.096])
        np.testing.assert_allclose(
            np.vstack([a.get_offsets() for a in zoom.collections]), residual
        )
        assert any(t.get_text() == "第 8、9 周" for t in main.texts)
    finally:
        plt.close(fig)
