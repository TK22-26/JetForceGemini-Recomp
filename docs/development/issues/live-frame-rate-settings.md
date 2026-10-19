# Live frame-rate settings

Status: OPEN enhancement / current limitation, reported by owner 2026-10-19.

FPS mode, custom cap and VSync are read once during renderer creation.
Applying them while playing currently requires stopping and restarting the
game. Fog strength already has a live message path. This is a host implementation
limitation, not an original game requirement.

A future live path must update renderer pacing/configuration and synchronize
presentation work while resetting interpolation history when changing between
Original and high-refresh modes. Preserve the original simulation timing and
CPU overlays. Validate Original/custom/unlimited transitions, VSync, reticles,
blur and frame pacing before removing the restart notice.

Queued behind the active rain investigation and owner-requested all-weapons
test tool. No live frame-rate implementation or verification yet.
