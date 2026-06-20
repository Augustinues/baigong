# DESIGN.md — 百工 Baigong

## Product
Agent 管理系统 / Dashboard for AI Agent orchestration

## Brand
- **Name**: 百工 Baigong
- **Tagline**: 让 AI Agent 像工匠一样协作
- **Audience**: 开发者、AI 从业者、企业内部用户
- **Tone**: Professional · Precise · Polished

## Colors

### Accent (Primary)
- **Indigo**: `hsl(235, 86%, 60%)` / `#4f5bf5`
- Hover: `hsl(235, 82%, 55%)` / `#3f4ae0`
- Active: `hsl(235, 78%, 48%)` / `#313bc4`

### Backgrounds
- **Canvas**: `hsl(230, 38%, 6%)` / `#0c0f1e` — Main background
- **Surface**: `hsl(230, 30%, 11%)` / `#141829` — Panels, sidebars
- **Elevated**: `hsl(230, 25%, 16%)` / `#1e2338` — Cards, inputs
- **Border**: `hsl(230, 20%, 22%)` / `#2a304a` — Dividers, outlines

### Text
- **Primary**: `hsl(220, 30%, 92%)` / `#e8ecf4` — Body, headings
- **Secondary**: `hsl(230, 18%, 56%)` / `#7c84a3` — Labels, hints
- **Muted**: `hsl(230, 15%, 40%)` / `#555c7a` — Disabled, placeholders

### Semantic
- **Success**: `hsl(160, 84%, 39%)` / `#10b981`
- **Warning**: `hsl(40, 96%, 50%)` / `#f59e0b`
- **Error**: `hsl(0, 84%, 60%)` / `#ef4444`
- **Info**: Same as Accent `#4f5bf5`

### Light Theme (daylight)
- **Canvas**: `hsl(210, 40%, 98%)` / `#f8fafc`
- **Surface**: `hsl(0, 0%, 100%)` / `#ffffff`
- **Elevated**: `hsl(210, 40%, 96%)` / `#f1f5f9`
- **Border**: `hsl(215, 20%, 90%)` / `#e2e8f0`
- **Text Primary**: `hsl(230, 40%, 10%)` / `#0f172a`
- **Text Secondary**: `hsl(230, 16%, 42%)` / `#64748b`

## Typography
- **Font**: `-apple-system, "PingFang SC", "SF Pro Text", "Helvetica Neue", sans-serif`
- **Code Font**: `"SF Mono", "Menlo", "Monaco", "Consolas", monospace`
- **Body**: 13px / 1.5 line-height
- **Small**: 11px / 1.4
- **Tiny**: 10px / 1.3 (code/logs only)
- **H1**: 15px / 1.3 (topbar title)
- **H2**: 13px / 1.4 (section titles)
- **Body line length**: 65-75ch max

## Spacing
- Base unit: 4px
- xs: 4px · sm: 8px · md: 12px · lg: 16px · xl: 24px · 2xl: 32px

## Border Radius
- Default: 6px
- Card: 8px
- Button: 6px
- Badge: 9999px (pill)
- Avatar: 6px

## Shadows
- Card: `0 1px 3px rgba(0,0,0,.3), 0 1px 2px rgba(0,0,0,.2)`
- Elevated: `0 4px 12px rgba(0,0,0,.4)`
- Modal: `0 8px 32px rgba(0,0,0,.5)`

## Motion
- Default: `150-200ms ease`
- Theme transition: `250ms ease`
- Pulse animation: `0.8s ease-in-out infinite`

## Anti-patterns (Do NOT use)
- ❌ Gray text on colored backgrounds → use tinted shade of bg hue
- ❌ Pure black `#000` or pure gray `#808080` → always tint
- ❌ Cards nested inside cards → avoid nested depth
- ❌ Bounce/elastic easing → feels dated
- ❌ Inter font (overused) → use system font stack
- ❌ Purple-to-blue gradients (AI cliché) → use solid indigo
- ❌ Rounded-square icon tile above every heading → overused pattern
- ❌ Emoji as primary icons → use SVG or text labels
- ❌ Placeholder text with muted gray → needs 4.5:1 contrast
- ❌ Harsh animations (>300ms) or no animation at all

## Component States
- **Hover**: Brightness shift on interactive elements, `150ms ease`
- **Active/Focus**: Bright accent border ring `1px` + subtle shadow
- **Disabled**: `opacity: 0.4`, `cursor: not-allowed`, no hover effect
- **Loading**: Pulse animation on skeleton/glyph
- **Selected**: Accent border + subtle bg tint

## Agent Status Colors
- **idle**: Muted secondary text (`#7c84a3`)
- **thinking**: Accent amber (`#f59e0b`) — pulse animation
- **acting**: Accent indigo (`#4f5bf5`) — pulse animation
- **done**: Success green (`#10b981`)
- **error**: Error red (`#ef4444`)
