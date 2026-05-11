from __future__ import annotations

import os
import math
from typing import TYPE_CHECKING, Callable

import pygame

from visualizer.layout import Layout, NodeLayout

if TYPE_CHECKING:
    from model.flow import Flow, SimpleEntity


def _draw_circle(
    screen: pygame.Surface,
    color: tuple[int, int, int],
    center: tuple[int, int],
    radius: int,
    border: tuple[int, int, int] | None = None,
) -> None:
    pygame.draw.circle(screen, color, center, radius)
    if border:
        pygame.draw.circle(screen, border, center, radius, width=2)


def _draw_arrow(
    screen: pygame.Surface,
    a: tuple[int, int],
    b: tuple[int, int],
    color: tuple[int, int, int] = (100, 100, 100),
    width: int = 2,
) -> None:
    pygame.draw.line(screen, color, a, b, width=width)
    angle = math.atan2(b[1] - a[1], b[0] - a[0])
    head_len = 10
    da = math.radians(25)
    x1 = int(b[0] - head_len * math.cos(angle - da))
    y1 = int(b[1] - head_len * math.sin(angle - da))
    x2 = int(b[0] - head_len * math.cos(angle + da))
    y2 = int(b[1] - head_len * math.sin(angle + da))
    pygame.draw.polygon(screen, color, [b, (x1, y1), (x2, y2)])


class AssetCache:
    def __init__(self, asset_dir: str) -> None:
        self._dir = asset_dir
        self._cache: dict[str, pygame.Surface] = {}

    def get(self, name: str | None) -> pygame.Surface | None:
        if name is None:
            return None
        if name in self._cache:
            return self._cache[name]
        path = os.path.join(self._dir, name)
        if os.path.exists(path):
            surf = pygame.image.load(path).convert_alpha()
            self._cache[name] = surf
            return surf
        return None


class Engine:
    def __init__(
        self,
        flow: Flow,
        layout: Layout | None = None,
        *,
        fps: int = 60,
        width: int = 1024,
        height: int = 768,
        asset_dir: str = "assets",
        num_runs: int = 1,
        run_duration: float | None = None,
        run_setup: Callable[[Flow], None] | None = None,
        pause_between_runs: bool = True,
        time_scale: float = 1.0,
    ) -> None:
        self.flow = flow
        self.layout = layout or Layout.from_flow(flow)
        self.fps = fps
        self.width = width
        self.height = height
        self.assets = AssetCache(asset_dir)
        self.paused = False
        self.speed = 1.0
        self.num_runs = num_runs
        self.run_duration = run_duration
        self.run_setup = run_setup
        self.pause_between_runs = pause_between_runs
        self.time_scale = time_scale
        self.current_run = 1
        self.results: list[dict] = []

        self._slider_dragging = False
        pad = 20
        self._slider_bar = pygame.Rect(pad, height - 40, width - pad * 2, 12)
        self._slider_min = 0.0
        self._slider_max = 5000.0

        pygame.init()
        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("promodel")
        self.clock = pygame.time.Clock()
        self.running = False
        self._font = pygame.font.SysFont("consolas", 20)

    def run(self) -> None:
        self.running = True
        for run in range(1, self.num_runs + 1):
            if not self.running:
                break
            self.current_run = run
            if self.run_setup:
                self.run_setup(self.flow)
            self._run_single()
            if self.running and hasattr(self.flow, "get_metrics"):
                self.results.append(self.flow.get_metrics())
            if self.running and run < self.num_runs and self.pause_between_runs:
                self._wait_between_runs()
        pygame.quit()

    def _run_single(self) -> None:
        while self.running:
            dt = self.clock.tick(self.fps) / 1000.0
            self._handle_events()
            if not self.paused:
                dt_eff = dt * self.speed * self.time_scale
                if self.run_duration is not None:
                    remaining = self.run_duration - self.flow.time
                    if dt_eff > remaining:
                        dt_eff = max(0.0, remaining)
                self.flow.tick(dt_eff)
            self._render()
            if self.run_duration is not None and self.flow.time >= self.run_duration:
                break

    def _wait_between_runs(self) -> None:
        waiting = True
        while waiting and self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        waiting = False
                    elif event.key == pygame.K_q:
                        self.running = False

            self._render_transition()
            self.clock.tick(self.fps)

    def _render_transition(self) -> None:
        overlay = pygame.Surface((self.width, self.height))
        overlay.set_alpha(180)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))

        lines = [
            f"Run {self.current_run} Complete",
            f"Completed: {self.flow.get_metrics()['completed']}",
            "",
            "Press SPACE to continue",
            "Press Q to quit",
        ]

        y = self.height // 2 - len(lines) * 15
        for line in lines:
            surf = self._font.render(line, True, (255, 255, 255))
            x = (self.width - surf.get_width()) // 2
            self.screen.blit(surf, (x, y))
            y += 30

        pygame.display.flip()

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    self.paused = not self.paused
                elif event.key == pygame.K_q:
                    self.running = False

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    mx, my = event.pos
                    handle_x = self._slider_bar.x + int(
                        (self.speed - self._slider_min)
                        / (self._slider_max - self._slider_min)
                        * self._slider_bar.width
                    )
                    if (
                        abs(mx - handle_x) < 15
                        and abs(my - self._slider_bar.centery) < 20
                    ):
                        self._slider_dragging = True

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    self._slider_dragging = False

            elif event.type == pygame.MOUSEMOTION:
                if self._slider_dragging:
                    mx = event.pos[0]
                    ratio = (mx - self._slider_bar.x) / self._slider_bar.width
                    ratio = max(0.0, min(1.0, ratio))
                    self.speed = self._slider_min + ratio * (
                        self._slider_max - self._slider_min
                    )

    def _render(self) -> None:
        self.screen.fill((30, 30, 30))

        for (a_name, b_name), data in self.flow.edges.items():
            a = self.layout.get(a_name)
            b = self.layout.get(b_name)
            _draw_arrow(self.screen, (a.x, a.y), (b.x, b.y))
            mid = ((a.x + b.x) // 2, (a.y + b.y) // 2)
            pygame.draw.circle(self.screen, (150, 150, 150), mid, 2)

        for name, data in self.flow.nodes.items():
            nl = self.layout.get(name)
            sprite = self.assets.get(nl.sprite)
            if sprite:
                rect = sprite.get_rect(center=(nl.x, nl.y))
                self.screen.blit(sprite, rect)
            else:
                _draw_circle(
                    self.screen, (60, 60, 80), (nl.x, nl.y), 24, border=(120, 120, 160)
                )

            q = len(data["queue"])
            if q:
                surf = self._font.render(str(q), True, (255, 200, 0))
                self.screen.blit(surf, (nl.x + 28, nl.y - 28))

        for e in self.flow.entities:
            pos = self._entity_pos(e)
            pygame.draw.circle(self.screen, e.color, pos, 6)

        bar = self._slider_bar
        pygame.draw.rect(self.screen, (50, 50, 50), bar, border_radius=3)
        ratio = (self.speed - self._slider_min) / (self._slider_max - self._slider_min)
        handle_x = bar.x + int(ratio * bar.width)
        pygame.draw.circle(self.screen, (200, 200, 200), (handle_x, bar.centery), 8)
        if self._slider_dragging:
            _draw_circle(
                self.screen,
                (0, 200, 255),
                (handle_x, bar.centery),
                10,
                border=(255, 255, 255),
            )

        # Draw run info
        run_text = f"Run {self.current_run} / {self.num_runs}"
        time_text = f"Time: {self.flow.time:.1f}"
        if self.run_duration is not None:
            time_text += f" / {self.run_duration:.1f}"
        spd_text = f"Speed: {self.speed:.0f}x"

        surf_run = self._font.render(run_text, True, (255, 255, 255))
        surf_time = self._font.render(time_text, True, (255, 255, 255))
        surf_spd = self._font.render(spd_text, True, (255, 255, 255))
        self.screen.blit(surf_run, (self.width - surf_run.get_width() - 20, 20))
        self.screen.blit(surf_time, (self.width - surf_time.get_width() - 20, 45))
        self.screen.blit(surf_spd, (self.width - surf_spd.get_width() - 20, 70))

        pygame.display.flip()

    def _entity_pos(self, e: SimpleEntity) -> tuple[int, int]:
        if e.current_node is not None:
            nl = self.layout.get(e.current_node)
            return (nl.x, nl.y)

        if hasattr(e, "_transit_target"):
            src_name = getattr(e, "_transit_src", None)
            if src_name:
                src = self.layout.get(src_name)
                dst = self.layout.get(e._transit_target)
                p = e.progress
                x = int(src.x + (dst.x - src.x) * p)
                y = int(src.y + (dst.y - src.y) * p)
                return (x, y)
        return (0, 0)
