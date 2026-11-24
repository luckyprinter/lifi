# Academy development handoff

The feature branch starts from `luckyprinter/lifi` main at `99f8fc6d1159101c3aa459b45deca8da28f1eba6`. Main already included the merged redesign, application atlas, source studio, practice, and the 88-file source inventory. Continue from the feature pull request and use the private Sites deployment for review. The GitHub Pages workflow publishes main.

## Changes

- Added an educational browser transfer lab alongside the physical signal journey.
- Added linkable code lessons, persistent learning progress, keyboard navigation, and reduced-motion handling.
- Kept the source reference pinned to canonical main. The physical-first Method 2 branch is an alternate development snapshot, so its line numbers and behavior should be re-audited before migrating the course.

## Limits

- The lab covers representative STREAM/OOK behavior. Hardware timing, analog noise, USB device communication, and DMA execution require physical or firmware-specific validation.
- Guided line-by-line coverage is curated. The Deep Dive provides the wider tracked-file and symbol inventory.
- Live source browsing depends on public GitHub availability. The immutable links identify the source used by the course.

## Design references

The uploaded clip was a development-tool roundup. Its architecture and UI audit resources informed linked source traces, responsive hierarchy, and keyboard and reduced-motion checks. The site uses the existing Academy design system and adds no runtime dependencies from those tools. The interactive course reference is [Designed to Scale](https://designed-to-scale.vercel.app/).
