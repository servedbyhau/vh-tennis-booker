# How it works

## Reading a Flutter app from the outside

uiautomator2 reads Android's accessibility tree. Flutter renders its own widgets, but
publishes a *semantics* tree to accessibility services, where visible text appears in
`content-desc` (not `text`). Every selector in this project therefore uses
`description=...` / `descriptionContains=...`.

Two consequences shaped the design:

1. **Only on-screen widgets exist.** Flutter builds lazily, so a time slot below the
   fold is absent from the tree until scrolled into view. `Booker.pick_slot` scrolls in
   small, slow swipes and taps only when the slot is fully visible and not covered by
   the sticky bottom button.
2. **Unlabeled widgets.** The consent checkbox is a plain clickable `View` with no
   label and `checkable=false`. It is located relative to its caption:

   ```
   [35,740][79,784]   View  clickable=true      <- checkbox
   [79,739][313,772]  View  "Tôi đã hiểu và đồng ý với "
   ```

   A candidate is accepted only if it is small, left of the caption and on the same
   row (`geometry.is_checkbox_beside`). Thresholds scale with screen width.

## "Coordinates" vs. elements

Every tap on Android is ultimately a touch at (x, y). The difference is where the point
comes from: here it is computed from the element's live bounds at the moment of the
tap, never stored. The cost is the query to the device (~50–200 ms), which is needed
anyway to know the button has appeared.

## Navigation

`Booker.go()` waits for a button, taps immediately, then waits for any selector of the
next screen. If the next screen does not appear within 2 s (tap swallowed by lag), it
taps again, up to 5 times.

After confirming, the script waits until the confirmation screen is gone (the ticket
screen is shown) before pressing Back. From the ticket screen, one Back returns to the
utilities list, where the next round begins.

## Lessons learned

- The first coordinate-based version failed because the emulator ran at **540×960**,
  not the assumed 900×1600. Label-based lookup removed the whole class of bugs.
- Measure before optimizing: every log line shows `+N.NNs` since the previous step.
