# Settings Page Card Content Design

**Date:** 2026-03-12  
**Scope:** Frontend-only settings page content redesign for CipherClip  
**Constraint:** Keep the current settings page UI layout and visual style. Only adjust the card sections and the options inside those cards.

## Goal

Redesign the **content structure** of the settings page without redesigning the page shell itself.

This means:

- keep the current top header layout
- keep the current single-page scrolling structure
- keep the current card-based visual style
- keep the current footer action area pattern
- only change the card grouping and the setting items inside each card

This document focuses on:

- which cards should exist
- what each card is responsible for
- which current options should move, stay, or be removed from those cards

## Explicit Direction

This redesign is **not** a new settings architecture.

It should **not**:

- introduce a sidebar
- split settings into a multi-panel preferences app
- redesign the top shell
- replace the current page with a new navigation model

It **should**:

- preserve the current UI structure in `SettingsView`
- preserve the current visual language already established by the frontend
- make the existing card sections feel cleaner, more logical, and easier to extend

## Current Page Shape To Keep

The existing page shape stays:

```text
+------------------------------------------------------------------+
| Settings                                              [Back]     |
| Configure CipherClip behavior, shortcuts, and storage.           |
+------------------------------------------------------------------+
| [General Card]                                                   |
| [Shortcuts Card]                                                 |
| [History Card]                                                   |
| [Recording Card]                                                 |
+------------------------------------------------------------------+
| Cancel                                                   Save    |
+------------------------------------------------------------------+
```

The redesign should still look structurally like this:

```text
+------------------------------------------------------------------+
| Settings                                              [Back]     |
| Configure CipherClip behavior, shortcuts, and storage.           |
+------------------------------------------------------------------+
| [Card 1]                                                         |
| [Card 2]                                                         |
| [Card 3]                                                         |
| [Card 4]                                                         |
| [Optional Card 5]                                                |
+------------------------------------------------------------------+
| Cancel                                                   Save    |
+------------------------------------------------------------------+
```

## Design Principle

The main issue is not the overall page layout. The issue is that some options currently live in the wrong card, some are mixed with different responsibilities, and some are not worth keeping.

So the redesign should follow these rules:

1. Keep each card focused on one responsibility.
2. Do not mix runtime actions with persistent preferences.
3. Do not mix dangerous actions with ordinary settings.
4. Keep the page readable in one vertical scroll.
5. Make future additions possible by adding rows to existing cards instead of redesigning the page again.

## Recommended Card Structure

Recommended settings cards:

1. General
2. Capture
3. Shortcuts
4. History & Storage
5. Data Management

This is still a single-page layout. The only change is the card grouping.

## Card 1: General

Purpose:

- app-level behavior
- window-level behavior
- simple global preferences

```text
+--------------------------------------------------+
| General                                          |
| Launch on Startup                     [toggle]   |
 |
+--------------------------------------------------+
```

Notes:

- `Launch on Startup` belongs here and should stay.



## Card 3: Shortcuts

Purpose:

- keyboard-related configuration only

```text
+--------------------------------------------------+
| Shortcuts                                        |
| Toggle Panel                          [input]    |
| Primary Action                        [input]    |
| Plain Text Paste                      [input]    |
| Toggle Pin                            [input]    |
| Delete Record                         [input]    |
| Restore Defaults                      [button]   |
+--------------------------------------------------+
```

Notes:

- Keep this as its own dedicated card.
- Even if shortcut editing is upgraded later, the card itself should remain.
- `Restore Defaults` still belongs here if it only resets shortcuts.
- If there is later a global restore action, that should not live here.

## Card 4: History & Storage

Purpose:

- retention counts
- storage information

```text
+--------------------------------------------------+
| History & Storage                                |
| Text Clip Limit                       [number]   |
| Image Clip Limit                      [number]   |
| Storage Path                          [readonly] |
Clear All History                [danger]   |
+--------------------------------------------------+
```

Notes:

- `Text Clip Limit` stays here.
- `Image Clip Limit` stays here.
- `Storage Path` stays here.
- This card should feel informational and configuration-oriented, not operational.
- Do not place destructive actions in this card.



## What To Remove From The Current Structure

### Remove the standalone Recording card

Current item:

- `Pause Recording`

Reason:

- it represents runtime state, not a saved preference
- it behaves more like a quick control than a settings value
- it does not belong in a persistent settings form

Recommendation:

- remove the `Recording` card from the settings page
- keep pause/resume control in the quick panel or other runtime control surface

## Mapping From Current Cards To New Cards

### Current `General`

- keep `Launch on Startup`
- keep `Close to Tray`
- conditionally keep or remove `Follow System Theme`

### Current `Shortcuts`

- keep all shortcut rows
- keep shortcut-only `Restore Defaults`

### Current `History`

- keep `Text Clip Limit`
- keep `Image Clip Limit`
- move `Record Images` to `Capture`
- keep `Storage Path`
- move `Clear Unpinned History` to `Data Management`

### Current `Recording`

- remove the whole card from settings

## Recommended Final Vertical Order

Recommended scroll order:

1. General
2. Capture
3. Shortcuts
4. History & Storage
5. Data Management

Reasoning:

- start with lightweight global behavior
- then capture behavior
- then keyboard workflows
- then storage and retention
- end with risky actions

This ordering keeps the page readable and predictable without changing the current overall UI structure.

## Visual Guidance

Because the outer UI remains unchanged, the redesign should keep the existing visual language:

- same card look
- same spacing system
- same header
- same footer action region
- same one-page flow

The only visual adjustment recommended here is:

- make the `Data Management` card feel more cautionary than the standard cards

That can be done with subtle danger emphasis, but not a completely different layout language.

## Minimal Wireframe

```text
+------------------------------------------------------------------+
| Settings                                              [Back]     |
| Configure CipherClip behavior, shortcuts, and storage.           |
+------------------------------------------------------------------+
| General                                                          |
| - Launch on Startup                                              |
| - Close to Tray                                                  |
| - Follow System Theme*                                           |
|                                                                  |
| Capture                                                          |
| - Record Text                                                    |
| - Record Rich Text                                               |
| - Record Images                                                  |
| - Record Files                                                   |
|                                                                  |
| Shortcuts                                                        |
| - Toggle Panel                                                   |
| - Primary Action                                                 |
| - Plain Text Paste                                               |
| - Toggle Pin                                                     |
| - Delete Record                                                  |
| - Restore Defaults                                               |
|                                                                  |
| History & Storage                                                |
| - Text Clip Limit                                                |
| - Image Clip Limit                                               |
| - Storage Path                                                   |
|                                                                  |
| Data Management                                                  |
| - Clear Unpinned History                                         |
+------------------------------------------------------------------+
| Cancel                                                   Save    |
+------------------------------------------------------------------+
```

## Recommendation

The best next implementation step is:

1. remove the `Recording` card
2. add a new `Capture` card
3. move `Record Images` into `Capture`
4. move `Clear Unpinned History` into `Data Management`
5. rename `History` to `History & Storage`
6. decide whether `Follow System Theme` is real enough to keep

## Next Design Pass

After this document, the next pass should define:

1. exact keep/remove/add list for each row
2. row labels and helper text
3. whether any new rows are needed in `Capture`
4. whether `Follow System Theme` should be removed now
