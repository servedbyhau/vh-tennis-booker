# Changelog

## 0.8.0
- Round 2 starts from the utilities list (one Back from the ticket screen).
- Wait for the ticket screen before navigating away; success is verified.
- Millisecond step timing in logs; fewer redundant device queries.
- Restructured into a package with config file, tests and CI.

## 0.7.0
- Scroll time slots into view; never tap a slot covered by the bottom button.

## 0.6.0
- Two rounds by default; checkbox must be level with its caption; position cached.

## 0.5.0
- Checkbox located as the clickable node left of its caption.
- Fallback coordinates expressed as screen ratios.

## 0.1.0 – 0.4.0
- Initial flow, retry-on-lag navigation, month navigation, dry-run mode.
