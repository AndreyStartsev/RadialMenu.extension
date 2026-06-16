$CX = 320
$CY = 320

# Radial definitions with increased distance from center and 6px gap between rings
# Central core is R=55. Level 1 starts at R=75, leaving a 20px space.
$L1_R_IN = 75
$L1_R_OUT = 155

$L2_R_IN = 161
$L2_R_OUT = 221

$L3_R_IN = 227
$L3_R_OUT = 287

# Parallel gap width in pixels (parallel to sector edge, constant width along the petal)
$GAP_WIDTH = 5.0
$OFFSET = $GAP_WIDTH / 2.0

$slots_level1 = @(
    @{ angle = 270; name = "BtnZoom"; slot = 1 }
    @{ angle = 315; name = "BtnCloseHidden"; slot = 2 }
    @{ angle = 0;   name = "BtnSync"; slot = 3 }
    @{ angle = 45;  name = "BtnSave"; slot = 4 }
    @{ angle = 90;  name = "Btn3D"; slot = 5 }
    @{ angle = 135; name = "BtnReveal"; slot = 6 }
    @{ angle = 180; name = "BtnThinLines"; slot = 7 }
    @{ angle = 225; name = "BtnDetailLevel"; slot = 8 }
)

$slots_level2 = @(
    @{ angle = 225; name = "BtnSub2_1"; slot = 9 }
    @{ angle = 270; name = "BtnSub2_2"; slot = 10 }
    @{ angle = 315; name = "BtnSub2_3"; slot = 11 }
    @{ angle = 0;   name = "BtnSub2_4"; slot = 12 }
    @{ angle = 45;  name = "BtnSub2_5"; slot = 13 }
)

$slots_level3 = @(
    @{ angle = 315; name = "BtnSub3_1"; slot = 14 }
    @{ angle = 0;   name = "BtnSub3_2"; slot = 15 }
    @{ angle = 45;  name = "BtnSub3_3"; slot = 16 }
)

function Get-SectorPathParallel($r_in, $r_out, $angle_center) {
    # Full sector span is 45 degrees
    $theta1 = $angle_center - 22.5
    $theta2 = $angle_center + 22.5
    
    $rad1 = $theta1 * [Math]::PI / 180.0
    $rad2 = $theta2 * [Math]::PI / 180.0
    
    # Boundary radial unit vectors
    $d1_x = [Math]::Cos($rad1)
    $d1_y = [Math]::Sin($rad1)
    $d2_x = [Math]::Cos($rad2)
    $d2_y = [Math]::Sin($rad2)
    
    # Inner offset direction vectors (offset by $OFFSET perpendicular to radial boundary)
    # Line 1 offset points towards increasing angle (counter-clockwise/interior)
    $n1_x = -$d1_y
    $n1_y = $d1_x
    
    # Line 2 offset points towards decreasing angle (clockwise/interior)
    $n2_x = $d2_y
    $n2_y = -$d2_x
    
    # Calculate starting point for Line 1 (on inner circle)
    $t_in = [Math]::Sqrt($r_in*$r_in - $OFFSET*$OFFSET)
    $p_in1_x = $CX + $OFFSET * $n1_x + $t_in * $d1_x
    $p_in1_y = $CY + $OFFSET * $n1_y + $t_in * $d1_y
    
    # Calculate ending point for Line 1 (on outer circle)
    $t_out = [Math]::Sqrt($r_out*$r_out - $OFFSET*$OFFSET)
    $p_out1_x = $CX + $OFFSET * $n1_x + $t_out * $d1_x
    $p_out1_y = $CY + $OFFSET * $n1_y + $t_out * $d1_y
    
    # Calculate starting point for Line 2 (on inner circle)
    $p_in2_x = $CX + $OFFSET * $n2_x + $t_in * $d2_x
    $p_in2_y = $CY + $OFFSET * $n2_y + $t_in * $d2_y
    
    # Calculate ending point for Line 2 (on outer circle)
    $p_out2_x = $CX + $OFFSET * $n2_x + $t_out * $d2_x
    $p_out2_y = $CY + $OFFSET * $n2_y + $t_out * $d2_y
    
    # Path: Move to inner1, Line to outer1, Arc to outer2 (sweep 1), Line to inner2, Arc to inner1 (sweep 0), Close
    $path = "M {0:F2},{1:F2} L {2:F2},{3:F2} A {4},{4} 0 0,1 {5:F2},{6:F2} L {7:F2},{8:F2} A {9},{9} 0 0,0 {10:F2},{11:F2} Z" -f $p_in1_x, $p_in1_y, $p_out1_x, $p_out1_y, $r_out, $p_out2_x, $p_out2_y, $p_in2_x, $p_in2_y, $r_in, $p_in1_x, $p_in1_y
    return $path
}

function Get-TextPos($r_in, $r_out, $angle_center, $w=80, $h=70) {
    $rad = $angle_center * [Math]::PI / 180.0
    $r_mid = ($r_in + $r_out) / 2.0
    
    $x_c = $CX + $r_mid * [Math]::Cos($rad)
    $y_c = $CY + $r_mid * [Math]::Sin($rad)
    
    $left = $x_c - $w / 2.0
    $top = $y_c - 12.0 # align icon's Y-center (offset 12px within 24x24) to the physical center of the sector
    return @($left, $top)
}

function Generate-Buttons($slots, $r_in, $r_out, $level_label) {
    Write-Output "<!-- ================= $level_label ================= -->"
    foreach ($info in $slots) {
        $p = Get-SectorPathParallel $r_in $r_out $info.angle
        $pos = Get-TextPos $r_in $r_out $info.angle
        $left = $pos[0]
        $top = $pos[1]
        
        Write-Output "            <!-- Slot $($info.slot) ($($info.name)) Center Angle $($info.angle) -->"
        Write-Output "            <Button Name=`"$($info.name)`" Style=`"{StaticResource SectorButtonStyle}`" Tag=`"$p`">"
        Write-Output "                <Canvas Width=`"640`" Height=`"640`">"
        Write-Output "                    <StackPanel Canvas.Left=`"$("{0:F2}" -f $left)`" Canvas.Top=`"$("{0:F2}" -f $top)`" Width=`"80`" Height=`"70`" VerticalAlignment=`"Center`">"
        Write-Output "                        <Grid Width=`"24`" Height=`"24`" Margin=`"0,0,0,3`" HorizontalAlignment=`"Center`">"
        Write-Output "                            <Image Name=`"$($info.name)Image`" Stretch=`"Uniform`" Width=`"22`" Height=`"22`" Visibility=`"Collapsed`"/>"
        Write-Output "                            <TextBlock Name=`"$($info.name)Emoji`" Text=`"`" FontSize=`"18`" HorizontalAlignment=`"Center`" VerticalAlignment=`"Center`"/>"
        Write-Output "                        </Grid>"
        Write-Output "                        <TextBlock Name=`"$($info.name)Label`" Text=`"`" Style=`"{StaticResource LabelStyle}`"/>"
        Write-Output "                    </StackPanel>"
        Write-Output "                </Canvas>"
        Write-Output "            </Button>"
        Write-Output ""
    }
}

Write-Output "--- START BUTTONS ---"
Generate-Buttons $slots_level1 $L1_R_IN $L1_R_OUT "LEVEL 1 BUTTONS"
Generate-Buttons $slots_level2 $L2_R_IN $L2_R_OUT "LEVEL 2 BUTTONS"
Generate-Buttons $slots_level3 $L3_R_IN $L3_R_OUT "LEVEL 3 BUTTONS"
Write-Output "--- END BUTTONS ---"
