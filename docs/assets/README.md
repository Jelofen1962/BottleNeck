# README media

`readme-hero.svg` is the large image at the top of the repository README. It is a project illustration, not a screenshot of a running installation.

To replace it with a real product screenshot:

1. Capture the application with sample data that contains no private names, email addresses, phone numbers or customer content.
2. Save the image as `docs/assets/readme-hero.webp` (wide images around 1600 × 650 work well).
3. Change the image source near the top of `README.md` from `docs/assets/readme-hero.svg` to `docs/assets/readme-hero.webp`.
4. Keep the screenshot current with the released UI; avoid mock counters or features that the release doesn't ship.

Keep the SVG source in the repository even after adding screenshots. It provides a clean fallback for documentation previews.
