# -*- coding: utf-8 -*-
"""
Pure-math radial geometry calculations.

All functions in this module use only the Python standard library (``math``)
and produce plain strings or tuples.  There are **zero** dependencies on
WPF, Revit, or any .NET assembly, making the module easy to unit-test.
"""

import math


def get_sector_path(cx, cy, r_in, r_out, angle_center, num_sectors,
                    gap_width):
    """Generate a WPF-compatible ``Path.Data`` string for one radial sector.

    The sector is drawn as a closed region between two concentric arcs
    (inner radius *r_in*, outer radius *r_out*) with parallel-offset gaps
    between adjacent sectors.

    Args:
        cx (float): X-coordinate of the radial centre.
        cy (float): Y-coordinate of the radial centre.
        r_in (float): Inner radius of the ring.
        r_out (float): Outer radius of the ring.
        angle_center (float): Centre angle of the sector in **degrees**
            (0° = right / 3-o'clock, increasing clockwise in screen
            coordinates).
        num_sectors (int): Total number of sectors dividing the full
            360° ring.
        gap_width (float): Visual gap between neighbouring sectors,
            measured as the perpendicular distance in pixels.

    Returns:
        str: A WPF mini-language path string
            (``M … L … A … L … A … Z``).
    """
    # Full sector angular span
    span = 360.0 / float(num_sectors)
    theta1 = angle_center - span / 2.0
    theta2 = angle_center + span / 2.0

    rad1 = math.radians(theta1)
    rad2 = math.radians(theta2)

    # Boundary radial unit vectors
    d1_x = math.cos(rad1)
    d1_y = math.sin(rad1)
    d2_x = math.cos(rad2)
    d2_y = math.sin(rad2)

    offset = float(gap_width) / 2.0

    # Perpendicular unit normals pointing inward to the sector
    n1_x = -d1_y
    n1_y = d1_x

    n2_x = d2_y
    n2_y = -d2_x

    # Solve for parameter t on inner/outer circles
    if r_in > offset:
        t_in = math.sqrt(r_in * r_in - offset * offset)
    else:
        t_in = 0.0

    if r_out > offset:
        t_out = math.sqrt(r_out * r_out - offset * offset)
    else:
        t_out = 0.0

    # Compute the four corner points of the sector
    p_in1_x = cx + offset * n1_x + t_in * d1_x
    p_in1_y = cy + offset * n1_y + t_in * d1_y

    p_out1_x = cx + offset * n1_x + t_out * d1_x
    p_out1_y = cy + offset * n1_y + t_out * d1_y

    p_in2_x = cx + offset * n2_x + t_in * d2_x
    p_in2_y = cy + offset * n2_y + t_in * d2_y

    p_out2_x = cx + offset * n2_x + t_out * d2_x
    p_out2_y = cy + offset * n2_y + t_out * d2_y

    # WPF mini-language path
    path = (
        "M {0:.2f},{1:.2f} "
        "L {2:.2f},{3:.2f} "
        "A {4},{4} 0 0,1 {5:.2f},{6:.2f} "
        "L {7:.2f},{8:.2f} "
        "A {9},{9} 0 0,0 {10:.2f},{11:.2f} Z"
    ).format(
        p_in1_x, p_in1_y,
        p_out1_x, p_out1_y,
        r_out,
        p_out2_x, p_out2_y,
        p_in2_x, p_in2_y,
        r_in,
        p_in1_x, p_in1_y,
    )
    return path


def get_text_position(cx, cy, r_in, r_out, angle_center, width=80,
                      height=70):
    """Compute the top-left position for a text/icon overlay centred on
    a sector.

    The overlay rectangle of size (*width* × *height*) is positioned so
    that its horizontal centre coincides with the midpoint of the sector
    arc (halfway between *r_in* and *r_out* at *angle_center*).  The
    vertical position is shifted upward by 12 px to better align an
    icon's visual centre.

    Args:
        cx (float): X-coordinate of the radial centre.
        cy (float): Y-coordinate of the radial centre.
        r_in (float): Inner radius of the ring.
        r_out (float): Outer radius of the ring.
        angle_center (float): Centre angle of the sector in degrees.
        width (float): Width of the overlay rectangle.  Defaults to 80.
        height (float): Height of the overlay rectangle.  Defaults to 70.

    Returns:
        tuple[float, float]: ``(left, top)`` coordinates for placing
        the overlay.
    """
    rad = math.radians(angle_center)
    r_mid = (r_in + r_out) / 2.0

    x_c = cx + r_mid * math.cos(rad)
    y_c = cy + r_mid * math.sin(rad)

    left = x_c - width / 2.0
    top = y_c - 12.0  # shift to align icon Y-center with sector center
    return left, top


def calculate_ring_radii(core_radius, petal_width, ring_gap, num_levels=3):
    """Compute inner/outer radius pairs for concentric rings.

    Rings are stacked outward from the core circle:

    * Ring 1 inner = *core_radius* + *ring_gap*
    * Ring 1 outer = ring 1 inner + *petal_width*
    * Ring 2 inner = ring 1 outer + *ring_gap*
    * … and so on.

    Args:
        core_radius (float): Radius of the central "core" circle.
        petal_width (float): Radial thickness of each ring.
        ring_gap (float): Gap between adjacent rings (and between
            the core and the first ring).
        num_levels (int): Number of concentric rings to compute.
            Defaults to 3.

    Returns:
        list[tuple[float, float]]: A list of ``(r_inner, r_outer)``
        tuples, one per level, ordered from innermost to outermost.
    """
    radii = []
    prev_outer = core_radius
    for _ in range(num_levels):
        r_in = prev_outer + ring_gap
        r_out = r_in + petal_width
        radii.append((r_in, r_out))
        prev_outer = r_out
    return radii


def calculate_effective_sectors(actual_count, max_angle):
    """Compute the virtual sector count with max-angle clamping.

    When a ring has few petals their natural angular span
    (``360 / actual_count``) may exceed *max_angle*.  In that case the
    petals are drawn as if there were more sectors (the "virtual" count)
    so that each petal never exceeds *max_angle* degrees.

    Args:
        actual_count (int): Number of real petals / items in the ring.
        max_angle (float): Maximum allowed angular span for a single
            sector, in degrees.

    Returns:
        int: The effective (virtual) sector count.  Always
        ``>= actual_count`` and ``>= 0``.  Returns ``0`` when
        *actual_count* is ``0``.
    """
    if actual_count <= 0:
        return 0
    natural_span = 360.0 / float(actual_count)
    if natural_span > max_angle:
        return max(actual_count, int(360.0 / max_angle))
    return actual_count
