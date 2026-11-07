# Controls and calibration

## Head mode (recommended starting point)

1. Run `setup-gestures.ps1` on a fresh checkout, then launch `start-gestures.cmd`.
2. Click **Start capture**. Close other camera applications if capture fails. Camera index 0 is the default; restart with another index if necessary.
3. Click **Calibrate neutral** and relax your face for three seconds.
4. Select **Head**, face straight ahead, and click **Center head / F6**.
5. Enable **Mouse-look**, keep game output unchecked, then press F8. Turn your head horizontally and nod vertically. If a direction feels reversed, use its Invert switch and re-arm.
6. Start with low look speed and increase gradually. Return to the centered pose to stop. F6 re-centers and disarms; F8 re-arms.
7. Enable **game output**, focus the original MW2 campaign, and press F8. F9 stops control.

The full-speed head scale is 20 degrees before the dead zone and response curve. This is velocity steering: maintaining a rotated pose continues turning. Normal mouse/keyboard controls remain available.

## Gestures

Smile fires once; raised eyebrows reload once. Relax between activations. Move the threshold sliders if resting expressions trigger too easily or deliberate expressions do not register. Configuration changes disarm output.

Optional **Gesture WASD** maps open mouth to forward, pursed lips to backward, and sideways mouth movement to strafing. Hold one gesture to move and relax to release. Test directions in preview. Turn movement gestures off if they conflict with your fire/reload expressions.

## Gaze mode (experimental)

Select **Gaze**, choose 5 or 9 targets, and click **Calibrate gaze**. Keep your head still and look at each dot. Escape cancels. Wait for the acceptance dialog; completing the dots does not guarantee a usable fit. Five targets use a linear fit; nine targets use a regularized quadratic fit. Nine targets are not necessarily better with noisy or glare-affected recordings.

Enable mouse-look and inspect Look X/Y in preview: left should be negative X, right positive X, up negative Y, down positive Y. Maintain the same screen, camera, and seating arrangement afterward. Calibration is session-local and must be repeated after restart. Head mode does not require this procedure.

The circular dead zone starts from resting-center jitter and remains adjustable. Entering its inner region stops motion without a smoothing tail. Glare, reflections, lighting, and head movement can make gaze unreliable. Successful fit checks are not evidence of accurate screen-point tracking.

## Input and recovery

Only foreground `iw4sp.exe` receives game output. Switching away releases movement and resets input accumulation. A missing/stale face or multiple faces pauses output while keeping arming enabled. Fresh tracking plus a neutral expression for 250 ms is required to resume. Explicit F9 stops remain disarmed until F8.

The dashboard shows the current foreground process, frame age, and pause reason. If input is not reaching MW2, stop the main controller with F9 and run `python input_test.py`. Its F6 reload, F7 mouse nudge, and F10 forward tests isolate Windows/game delivery from gesture detection. Close that tool afterward: its F6 conflicts with head centering.

Try windowed mode and equal privilege levels if the game ignores input. No code injection, game-memory modification, or bypass of input restrictions is provided. Stop hotkeys require the application to remain responsive.

Frames are processed locally without recording. The active camera controller is separate from the experimental Cortex prototype. Do not run both simultaneously.
