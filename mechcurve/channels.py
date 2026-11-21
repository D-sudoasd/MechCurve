"""Physical channel names and conversion factors to the exported canonical units."""

import math

TIME = {"s": 1, "sec": 1, "ms": 0.001, "min": 60, "h": 3600}
LENGTH = {
    "mm": 1,
    "um": 0.001,
    "µm": 0.001,
    "μm": 0.001,
    "nm": 1e-6,
    "cm": 10,
    "in": 25.4,
    "inch": 25.4,
    "m": 1000,
}
FORCE = {
    "n": 1,
    "kn": 1000,
    "lbf": 4.4482216152605,
    "kip": 4448.2216152605,
    "mn": 0.001,
    "µn": 1e-6,
    "μn": 1e-6,
}
STRAIN = {"%": 1, "％": 1, "1": 100, "-": 100, "mm/mm": 100}
STRESS = {
    "mpa": 1,
    "n/mm2": 1,
    "n/mm²": 1,
    "gpa": 1000,
    "psi": 0.006894757293168,
    "ksi": 6.894757293168,
    "kpa": 0.001,
    "pa": 1e-6,
}
COLUMNS = {
    "time_s": (("time", "时间", "elapsed time"), TIME),
    "extension_mm": (
        ("extension", "displacement", "位移", "横梁位移", "crosshead displacement"),
        LENGTH,
    ),
    "force_N": (
        (
            "load",
            "force",
            "力",
            "载荷",
            "加载力",
            "compressive force",
            "压缩载荷",
            "peel force",
            "剥离力",
        ),
        FORCE,
    ),
    "strain_pct": (
        (
            "tensile strain",
            "engineering strain",
            "strain",
            "应变",
            "工程应变",
            "compressive strain",
            "压缩应变",
            "creep strain",
            "蠕变应变",
        ),
        STRAIN,
    ),
    "stress_MPa": (
        (
            "tensile stress",
            "engineering stress",
            "stress",
            "应力",
            "工程应力",
            "compressive stress",
            "压缩应力",
            "relaxation stress",
            "松弛应力",
        ),
        STRESS,
    ),
    "deflection_mm": (("deflection", "flexural deflection", "挠度"), LENGTH),
    "flexural_stress_MPa": (("flexural stress", "弯曲应力"), STRESS),
    "flexural_strain_pct": (("flexural strain", "弯曲应变"), STRAIN),
    "shear_stress_MPa": (("shear stress", "剪切应力", "切应力"), STRESS),
    "shear_strain_pct": (("shear strain", "剪切应变"), STRAIN),
    "torque_Nm": (
        ("torque", "moment of torque", "扭矩", "扭转力矩"),
        {
            "nm": 1,
            "n·m": 1,
            "n*m": 1,
            "n m": 1,
            "nmm": 0.001,
            "n·mm": 0.001,
            "n*mm": 0.001,
        },
    ),
    "angle_deg": (
        ("angle", "twist", "rotation", "扭转角", "转角"),
        {"deg": 1, "°": 1, "度": 1, "rad": 180 / math.pi},
    ),
    "depth_mm": (
        ("indentation depth", "penetration depth", "depth", "压入深度", "压痕深度"),
        LENGTH,
    ),
    "cycle_count": (
        ("cycle", "cycles", "cycle count", "循环数", "周次"),
        {"cycles": 1, "cycle": 1, "1": 1, "": 1},
    ),
    "amplitude_MPa": (("stress amplitude", "应力幅"), STRESS),
    "stiffness_N_mm": (("stiffness", "刚度"), {"n/mm": 1, "kn/mm": 1000, "n/m": 0.001}),
    "peel_mm": (("peel travel", "peel displacement", "剥离位移"), LENGTH),
}
# Legacy axial point dictionaries have always contained these five keys.
AXIAL = ("time_s", "extension_mm", "force_N", "strain_pct", "stress_MPa")
