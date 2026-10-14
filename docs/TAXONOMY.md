# The taxonomy, for contributors

Full research write-up: <https://brunomartignago.github.io/pages/research1.html>
Machine-readable definition: [`taxonomies/web-ui.yaml`](../taxonomies/web-ui.yaml)

## The idea in one paragraph
A web page combines **graphic components**, which follow rules, with **culture** (the audience), which varies. If the audience is held constant, the components should form recurring patterns across pages and flows. To find those patterns, every visible element is described along three independent axes, and the page is split into template sections. Stacking many pages' templates reveals **archetypes** (the recurring structure) and **incidences** (variations of it).

## Element axes: Form × Function × Component
Each element box gets **one value on each axis**. Assigning several labels to one box is what off-the-shelf tools couldn't do, and it's why this tool exists.

| Axis | Question | Values |
|---|---|---|
| **Form** | What does it look like? | Typo, Image, Icon, Space |
| **Function** | What does it do? | Dropdown, Radio button, Checkbox, Text input, Label, Text, Breadcrumb, Button, Link, Ad, Tag, Heading, Illustration |
| **Component** | What is it part of? | Carousel, Card, Table, Search bar, Banner, Menu, Filter, Tab, List item, Blank (none) |

Examples: a nav link is Typo · Link · Menu, a product thumbnail is Image · Link · Card, and a paragraph is Typo · Text · Blank.

## Template sections (stored as the `Taxonomy` attribute)
- **Header**: the top of the page (logo, navigation, search, login), usually `<header>`.
- **Sub-header**: between the header and the body (breadcrumbs, filters, secondary calls-to-action). Optional.
- **Footer**: the bottom (site map, contact, links), usually `<footer>`.
- **Columns**: body regions 20–100% of the body width. *Column 0* means a single-column section, and *Column 1…5* number columns left to right.
- **Panel**: a first or last column narrower than 20% of page width (*Left/Right Panel*).
- **Menu**: a panel where at least 50% of the elements are links (*Left/Right Menu*).
- **Overlay**: elements layered on the z-axis (modals, sticky bars). They're mapped but excluded from templates. *(Proposed for the tool.)*

## Template concepts
- **Template**: the page reduced to its section blocks.
- **Summarized template**: the sections packed, with blank space removed, into a fixed 24:25 rectangle, so pages of any length are comparable.
- **Archetype**: the structure that appears when summarized templates are stacked at 100/N % opacity.
- **Incidence**: a variation derived from an archetype.

## Proposing a change
1. Open a **taxonomy proposal** issue that gives the new value, the axis, 2–3 screenshots of real examples, and why existing values don't fit.
2. If accepted, add it to the YAML with `status: proposed` and a unique `key`.
3. Renaming or removing an existing value requires a data migration. Existing values are research data.

## Using your own taxonomy
Copy `web-ui.yaml`, change the attributes and options, and point a project at it in `project.yaml`. The UI, keyboard map, presets and exporters are all generated from the file.
