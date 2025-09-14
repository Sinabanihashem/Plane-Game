# space_2_5d_full.py
# 2.5D mobile-friendly space shooter (Pygame)
# Uses provided images:
#   player: file_00000000d2046243b1a262bb3cec5918.png
#   enemy:  file_000000007cc4624380a676be6d71fb1c.png
# Put fallen_down.mp3 in same folder.
# Optional sounds: shoot.wav, explosion.wav, power.wav

import pygame, random, os, math, sys, time
pygame.init()
try:
    pygame.mixer.init()
except:
    pass

# ---------------- Screen setup (mobile friendly) ----------------
info = pygame.display.Info()
WIDTH = info.current_w or 480
HEIGHT = info.current_h or 800
# Use FULLSCREEN; avoids (0,0) SCALED bug on some phones
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)
pygame.display.set_caption("Sky Defender 2.5D - @kawasakl_ninja")
clock = pygame.time.Clock()
FPS = 60

# ---------------- Layout ----------------
PANEL_H = int(100 * (WIDTH/480))   # bottom panel height
PLAY_H = HEIGHT - PANEL_H

# ---------------- Colors & Fonts ----------------
WHITE = (255,255,255)
BLACK = (0,0,0)
RED = (220,60,60)
GREEN = (80,200,100)
YELLOW = (230,210,60)
UI_BG = (18,18,28)
GRAY = (42,42,50)
FONT = pygame.font.SysFont("Arial", max(14, int(16*(WIDTH/480))))
BIG = pygame.font.SysFont("Arial", max(20, int(30*(WIDTH/480))))

# ---------------- Assets loader ----------------
def try_load_image(name, size=None):
    if os.path.exists(name):
        try:
            img = pygame.image.load(name).convert_alpha()
            if size:
                img = pygame.transform.smoothscale(img, size)
            return img
        except Exception as e:
            print("Image load error:", name, e)
    return None

def try_load_sound(name):
    if os.path.exists(name):
        try:
            return pygame.mixer.Sound(name)
        except Exception as e:
            print("Sound load error:", name, e)
    return None

# Provided asset filenames
PLAYER_IMG_FILE = "file_00000000d2046243b1a262bb3cec5918.png"
ENEMY_IMG_FILE  = "file_000000007cc4624380a676be6d71fb1c.png"
IMG_PLAYER = try_load_image(PLAYER_IMG_FILE, (96,72))
IMG_ENEMY  = try_load_image(ENEMY_IMG_FILE, (64,48))

# background layers (try load up to 3 layers named bg_layer1.png etc)
IMG_BG_LAYERS = []
for i in range(1,4):
    im = try_load_image(f"bg_layer{i}.png", (WIDTH, PLAY_H))
    if im: IMG_BG_LAYERS.append(im)

# sounds
SND_SHOOT = try_load_sound("shoot.wav")
SND_EXPLODE = try_load_sound("explosion.wav")
SND_POWER = try_load_sound("power.wav")

# music
MUSIC = None
music_file = os.path.join(os.path.dirname(__file__), "fallen_down.mp3")
if os.path.exists(music_file):
    try:
        pygame.mixer.music.load(music_file)
        pygame.mixer.music.set_volume(0.30)  # menu low
        pygame.mixer.music.play(-1)
        MUSIC = True
    except Exception as e:
        print("Music load failed:", e)

# ---------------- Highscore ----------------
HS_FILE = "highscore.txt"
def load_highscore():
    try:
        with open(HS_FILE,"r") as f:
            return int(f.read().strip() or "0")
    except:
        return 0
def save_highscore(v):
    try:
        with open(HS_FILE,"w") as f:
            f.write(str(int(v)))
    except:
        pass

# ---------------- Helpers ----------------
def draw_text(surf, txt, x, y, font=FONT, col=WHITE, center=False):
    r = font.render(txt, True, col)
    if center:
        surf.blit(r, (int(x - r.get_width()/2), int(y - r.get_height()/2)))
    else:
        surf.blit(r, (int(x), int(y)))

def clamp(v, a, b): return max(a, min(b, v))

# ---------------- Entities ----------------
class Player:
    def __init__(self):
        self.w = 96 if IMG_PLAYER else int(64*(WIDTH/480))
        self.h = 72 if IMG_PLAYER else int(48*(WIDTH/480))
        self.x = WIDTH//2
        self.y = PLAY_H - self.h - 32
        self.speed = 6.0 * (WIDTH/480)
        self.hp = 6
        self.weapon_level = 0    # permanent weapon level from pickups/upgrades (0..2)
        self.temp_multi_until = 0  # timestamp until which multi-shot powerup active
        self.last_shot = 0
        self.shot_cool = 320     # ms (lower => faster)
        self.damage = 1
        self.tilt = 0.0

    def effective_weapon(self):
        # if temporary multi active, return highest (2)
        if time.time() < self.temp_multi_until:
            return 2
        return self.weapon_level

    def draw(self, surf):
        tilt_angle = -self.tilt * 12
        if IMG_PLAYER:
            img = IMG_PLAYER
            if abs(tilt_angle) > 1:
                img = pygame.transform.rotozoom(IMG_PLAYER, tilt_angle, 1.0)
            r = img.get_rect(center=(int(self.x), int(self.y)))
            surf.blit(img, r.topleft)
        else:
            pts = [(self.x, self.y - self.h//2),(self.x - self.w//2, self.y + self.h//2),(self.x + self.w//2, self.y + self.h//2)]
            pygame.draw.polygon(surf, (70,140,220), pts)
            pygame.draw.polygon(surf, WHITE, pts, 2)

    def move_toward(self, tx, ty, lerp=0.24):
        self.x += (tx - self.x) * lerp
        self.y += (ty - self.y) * lerp
        self.x = clamp(self.x, self.w//2, WIDTH - self.w//2)
        self.y = clamp(self.y, self.h//2+8, PLAY_H - self.h//2 - 8)
        # approximate tilt
        desired_tilt = (tx - self.x) / (WIDTH/6)
        self.tilt += (desired_tilt - self.tilt) * 0.18

    def can_shoot(self):
        return pygame.time.get_ticks() - self.last_shot >= self.shot_cool

    def shoot(self):
        self.last_shot = pygame.time.get_ticks()
        bullets = []
        w = self.effective_weapon()
        if w == 0:
            bullets.append(Bullet(self.x, self.y - self.h//2 - 6, -14, self.damage))
        elif w == 1:
            bullets.append(Bullet(self.x - 12, self.y - self.h//2 - 6, -14, self.damage))
            bullets.append(Bullet(self.x + 12, self.y - self.h//2 - 6, -14, self.damage))
        else: # triple
            bullets.append(Bullet(self.x, self.y - self.h//2 - 6, -14, self.damage))
            bullets.append(Bullet(self.x - 16, self.y - self.h//2 + 2, -12, self.damage))
            bullets.append(Bullet(self.x + 16, self.y - self.h//2 + 2, -12, self.damage))
        if SND_SHOOT: SND_SHOOT.play()
        return bullets

class Bullet:
    def __init__(self, x, y, vy, dmg):
        self.x = x; self.y = y; self.vy = vy
        self.r = int(6*(WIDTH/480))
        self.damage = dmg
        self.color = YELLOW

    def update(self):
        self.y += self.vy
        return not (self.y < -60 or self.y > HEIGHT + 60)

    def draw(self, surf):
        pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), self.r)

    def rect(self):
        return pygame.Rect(int(self.x-self.r), int(self.y-self.r), int(self.r*2), int(self.r*2))

class Enemy:
    def __init__(self, level=1, kind="normal"):
        self.kind = kind
        self.level = level
        if kind == "boss":
            self.base_size = int(130*(WIDTH/480))
            self.base_z = 900
            self.hp = int(8 + 4*level + random.randint(0,6))
            self.speed = 1.1 + 0.06*level
            self.score = 3 + level
        else:
            self.base_size = int(56*(WIDTH/480))
            self.base_z = random.randint(300, 700)
            self.hp = max(1, int(1 + level*0.9 + random.choice([0,1])))
            self.speed = 2.0 + level*0.15 + random.random()*0.6
            self.score = 1
        self.spawn_x = random.randint(self.base_size//2, WIDTH - self.base_size//2)
        self.z = self.base_z
        self.phase = random.random() * 7
        self.update_screen_pos()

    def update_screen_pos(self):
        near = 80
        far = max(350, self.base_z)
        zc = clamp(self.z, near, far)
        t = (far - zc) / (far - near)  # 0..1 (1 = close)
        top_y = 40
        bottom_y = PLAY_H - 140
        self.size = max(12, int(self.base_size * (0.6 + 1.4 * t)))
        self.y = int(top_y + (bottom_y - top_y) * (1 - zc/far))
        self.x = int(self.spawn_x + math.sin(time.time() + self.phase) * 16 * (1 - zc/far))

    def update(self):
        # move toward player in z (reduce z)
        self.z -= self.speed
        self.update_screen_pos()
        # return False if passed the "near" threshold -> triggers game over
        return self.z > 40

    def draw(self, surf):
        rect = pygame.Rect(int(self.x - self.size//2), int(self.y - self.size//2), int(self.size), int(self.size))
        if IMG_ENEMY and self.kind == "normal":
            try:
                img = pygame.transform.smoothscale(IMG_ENEMY, (self.size, max(12, int(self.size*0.8))))
                surf.blit(img, img.get_rect(center=(self.x, self.y)).topleft)
            except:
                pygame.draw.rect(surf, RED, rect, border_radius=8)
        else:
            pygame.draw.rect(surf, RED if self.kind == "normal" else (150,40,40), rect, border_radius=8)
        # hp bar
        total = max(1, self.hp)
        bar_w = int(self.size * (max(0, self.hp) / total))
        pygame.draw.rect(surf, (40,40,40), (rect.left, rect.top - 8, self.size, 6))
        pygame.draw.rect(surf, GREEN, (rect.left, rect.top - 8, bar_w, 6))

    def rect(self):
        return pygame.Rect(int(self.x - self.size//2), int(self.y - self.size//2), int(self.size), int(self.size))

class Particle:
    def __init__(self, x, y, color):
        self.x = x; self.y = y
        self.vx = random.uniform(-2,2) * (WIDTH/480)
        self.vy = random.uniform(-3,0) * (WIDTH/480)
        self.life = random.randint(12,26)
        self.color = color
        self.size = random.randint(2,5)

    def update(self):
        self.x += self.vx; self.y += self.vy
        self.vy += 0.12
        self.life -= 1
        return self.life > 0

    def draw(self, surf):
        if self.life > 0:
            pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), max(1,self.size))

class PowerUp:
    def __init__(self, x, y, kind):
        self.x = x; self.y = y; self.kind = kind; self.vy = 1.2 * (WIDTH/480)
        self.size = int(14*(WIDTH/480))

    def update(self):
        self.y += self.vy
        return self.y - self.size <= PLAY_H

    def draw(self, surf):
        col = GREEN if self.kind == "hp" else YELLOW
        pygame.draw.circle(surf, col, (int(self.x), int(self.y)), self.size)
        draw_text(surf, "H" if self.kind=="hp" else "P", int(self.x-6), int(self.y-8), FONT, WHITE)

    def rect(self):
        return pygame.Rect(int(self.x-self.size), int(self.y-self.size), int(self.size*2), int(self.size*2))

# ---------------- Game manager ----------------
class Game:
    def __init__(self):
        self.player = Player()
        self.bullets = []
        self.enemies = []
        self.particles = []
        self.powerups = []
        self.score = 0
        self.highscore = load_highscore()
        self.spawn_timer = pygame.time.get_ticks()
        self.spawn_interval_ms = 1100
        self.start_time = pygame.time.get_ticks()
        self.state = "menu"   # menu, playing, gameover
        self.difficulty = "Normal"
        self.upgrades = {
            "power": {"cost": 6, "level": 0},
            "firerate": {"cost": 7, "level": 0},
            "hp": {"cost": 7, "level": 0}
        }
        self.enemy_hp_mul = 1.0
        self.enemy_speed_mul = 1.0
        self.points_per_kill = 1
        self.boss_chance = 0.03

    def set_difficulty(self, d):
        self.difficulty = d
        if d == "Easy":
            self.enemy_hp_mul = 0.85; self.enemy_speed_mul = 0.9; self.spawn_interval_ms = 1400; self.boss_chance = 0.01; self.points_per_kill = 1
        elif d == "Normal":
            self.enemy_hp_mul = 1.0; self.enemy_speed_mul = 1.0; self.spawn_interval_ms = 1100; self.boss_chance = 0.03; self.points_per_kill = 1
        else:
            self.enemy_hp_mul = 1.25; self.enemy_speed_mul = 1.1; self.spawn_interval_ms = 800; self.boss_chance = 0.06; self.points_per_kill = 1
        self.start_game()

    def start_game(self):
        self.player = Player()
        self.bullets = []
        self.enemies = []
        self.particles = []
        self.powerups = []
        self.score = 0
        self.spawn_timer = pygame.time.get_ticks()
        self.start_time = pygame.time.get_ticks()
        self.state = "playing"
        try:
            if MUSIC:
                pygame.mixer.music.set_volume(0.55)
        except:
            pass

    def end_game(self):
        self.state = "gameover"
        if self.score > self.highscore:
            self.highscore = self.score
            save_highscore(self.highscore)
        try:
            if MUSIC:
                pygame.mixer.music.set_volume(0.28)
        except:
            pass

    def spawn_enemy(self):
        level = 1 + int((pygame.time.get_ticks() - self.start_time) / 12000) + min(8, self.score//12)
        if random.random() < min(0.12, self.boss_chance + level*0.002):
            e = Enemy(level, kind="boss")
        else:
            e = Enemy(level, kind="normal")
        e.hp = max(1, int(e.hp * self.enemy_hp_mul))
        e.speed *= self.enemy_speed_mul
        self.enemies.append(e)

    def purchase(self, key):
        if key not in self.upgrades: return
        info = self.upgrades[key]
        if self.score >= info["cost"]:
            self.score -= info["cost"]
            info["level"] += 1
            if key == "power":
                self.player.damage += 1
            elif key == "firerate":
                self.player.shot_cool = max(90, int(self.player.shot_cool * 0.82))
            elif key == "hp":
                self.player.hp += 1
            info["cost"] = int(info["cost"] * 1.9)
            if SND_POWER: SND_POWER.play()

    def update(self):
        if self.state != "playing":
            return

        now = pygame.time.get_ticks()
        if now - self.spawn_timer >= self.spawn_interval_ms:
            self.spawn_enemy()
            self.spawn_timer = now
            self.spawn_interval_ms = max(420, int(self.spawn_interval_ms * 0.994))

        # bullets update
        for b in self.bullets[:]:
            alive = b.update()
            if not alive:
                try: self.bullets.remove(b)
                except: pass

        # enemies update
        for e in self.enemies[:]:
            alive = e.update()
            if not alive:
                # enemy passed -> game over
                self.end_game()
                return

        # collisions bullets -> enemies
        for b in self.bullets[:]:
            br = b.rect()
            hit = False
            for e in self.enemies[:]:
                if br.colliderect(e.rect()):
                    e.hp -= b.damage
                    try: self.bullets.remove(b)
                    except: pass
                    hit = True
                    if e.hp <= 0:
                        # kill
                        self.score += self.points_per_kill
                        r = random.random()
                        if r < 0.12:
                            self.powerups.append(PowerUp(e.x, e.y, "hp"))
                        elif r < 0.22:
                            self.powerups.append(PowerUp(e.x, e.y, "multi"))
                        for _ in range(8):
                            self.particles.append(Particle(e.x + random.uniform(-8,8), e.y + random.uniform(-6,6), YELLOW))
                        if SND_EXPLODE: SND_EXPLODE.play()
                        try: self.enemies.remove(e)
                        except: pass
                    break
            if hit: continue

        # powerups update / pickup
        for pu in self.powerups[:]:
            ok = pu.update()
            if not ok:
                try: self.powerups.remove(pu)
                except: pass
                continue
            if pu.rect().colliderect(pygame.Rect(self.player.x - self.player.w//2, self.player.y - self.player.h//2, self.player.w, self.player.h)):
                if pu.kind == "hp":
                    self.player.hp += 1
                else:  # multi (P) powerup
                    self.player.temp_multi_until = time.time() + 20.0  # 20 seconds duration
                try: self.powerups.remove(pu)
                except: pass
                if SND_POWER: SND_POWER.play()

        # particles update
        for p in self.particles[:]:
            ok = p.update()
            if not ok:
                try: self.particles.remove(p)
                except: pass

        # enemy collision with player
        for e in self.enemies[:]:
            enemy_rect = e.rect()
            player_rect = pygame.Rect(int(self.player.x - self.player.w//2), int(self.player.y - self.player.h//2), int(self.player.w), int(self.player.h))
            if enemy_rect.colliderect(player_rect):
                self.player.hp -= 1
                for _ in range(6):
                    self.particles.append(Particle(self.player.x + random.uniform(-6,6), self.player.y + random.uniform(-6,6), RED))
                try: self.enemies.remove(e)
                except: pass
                if SND_EXPLODE: SND_EXPLODE.play()
                if self.player.hp <= 0:
                    self.end_game()
                    return

    def draw(self, surf):
        # background layers parallax
        if IMG_BG_LAYERS:
            for i,layer in enumerate(IMG_BG_LAYERS):
                speed = 0.1 + 0.18 * i
                offset = int((time.time()*30*speed + self.player.x*0.06*(i+1)) % WIDTH)
                surf.blit(layer, (-offset, 0))
                surf.blit(layer, (-offset + WIDTH, 0))
        else:
            surf.fill((6,10,20))
            for si in range(60):
                sx = (si*73 + int(time.time()*60)) % WIDTH
                sy = (si*37) % PLAY_H
                pygame.draw.circle(surf, (160,160,200), (sx, sy), 1)

        # draw enemies by depth (far -> back first)
        sorted_enemies = sorted(self.enemies, key=lambda e: e.z, reverse=True)
        for e in sorted_enemies:
            e.draw(surf)

        # bullets, powerups, particles
        for b in self.bullets: b.draw(surf)
        for pu in self.powerups: pu.draw(surf)
        for p in self.particles: p.draw(surf)

        # player
        self.player.draw(surf)

        # bottom HUD with upgrade buttons placed higher (so easy to tap)
        # We'll place upgrade buttons above bottom edge so they are reachable
        hud_y = PLAY_H - int(64 * (WIDTH/480))
        pygame.draw.rect(surf, UI_BG, (0, hud_y, WIDTH, PANEL_H + int(64*(WIDTH/480))))
        draw_text(surf, f"Score: {self.score}", 12, hud_y + 6)
        draw_text(surf, f"HP: {self.player.hp}", WIDTH - 140, hud_y + 6)
        draw_text(surf, f"Weapon: {['SINGLE','DUAL','TRIPLE'][self.player.weapon_level]}", 12, hud_y + 36)
        draw_text(surf, f"Damage: {self.player.damage}", 12, hud_y + 64)
        draw_text(surf, f"Highscore: {self.highscore}", WIDTH - 200, hud_y + 36)
        draw_text(surf, f"Creator: @kawasakl_ninja", WIDTH - 260, hud_y + 64)

        # draw upgrade buttons above panel (easier to tap)
        pad = int(12*(WIDTH/480))
        bw = int((WIDTH - pad*5) / 3)
        bx = pad
        by = hud_y - int(56*(WIDTH/480))  # moved up
        pygame.draw.rect(surf, GRAY, (bx, by, bw, 48), border_radius=10)
        draw_text(surf, f"Power + (cost {self.upgrades['power']['cost']})", bx + bw//2, by + 24, center=True)
        bx += bw + pad
        pygame.draw.rect(surf, GRAY, (bx, by, bw, 48), border_radius=10)
        draw_text(surf, f"FireRate (cost {self.upgrades['firerate']['cost']})", bx + bw//2, by + 24, center=True)
        bx += bw + pad
        pygame.draw.rect(surf, GRAY, (bx, by, bw, 48), border_radius=10)
        draw_text(surf, f"HP +1 (cost {self.upgrades['hp']['cost']})", bx + bw//2, by + 24, center=True)

    def click_upgrade_area(self, pos):
        mx,my = pos
        pad = int(12*(WIDTH/480))
        bw = int((WIDTH - pad*5) / 3)
        bx = pad
        by = PLAY_H - int(64 * (WIDTH/480)) - int(56*(WIDTH/480))
        r1 = pygame.Rect(bx, by, bw, 48)
        r2 = pygame.Rect(bx + bw + pad, by, bw, 48)
        r3 = pygame.Rect(bx + 2*(bw + pad), by, bw, 48)
        if r1.collidepoint(pos):
            self.purchase("power"); return True
        if r2.collidepoint(pos):
            self.purchase("firerate"); return True
        if r3.collidepoint(pos):
            self.purchase("hp"); return True
        return False

# ---------------- Main loop ----------------
game = Game()
# reduce music volume in menu if playing
if MUSIC:
    try:
        pygame.mixer.music.set_volume(0.28)
    except:
        pass

touch_pos = None
shooting = False

running = True
while running:
    dt = clock.tick(FPS)
    for ev in pygame.event.get():
        if ev.type == pygame.QUIT:
            running = False
        elif ev.type == pygame.MOUSEBUTTONDOWN:
            mx,my = ev.pos
            if game.state == "menu":
                # menu buttons centered
                bw = int(110 * (WIDTH/480)); pad = int(20*(WIDTH/480))
                x0 = WIDTH//2 - int(1.5*bw + pad)
                ry = HEIGHT//2 + 20
                for i,lab in enumerate(["Easy","Normal","Hard"]):
                    rx = x0 + i*(bw+pad)
                    if rx <= mx <= rx + bw and ry <= my <= ry + 56:
                        game.set_difficulty(lab)
                        break
            elif game.state == "playing":
                # if click within upgrade area (we positioned it above bottom), use it
                if my >= PLAY_H - int(56*(WIDTH/480)) - int(64*(WIDTH/480)):
                    consumed = game.click_upgrade_area((mx,my))
                    if not consumed:
                        # toggle pause -> go to menu
                        game.state = "menu"
                        if MUSIC:
                            try: pygame.mixer.music.set_volume(0.28)
                            except: pass
                else:
                    shooting = True
                    touch_pos = (mx,my)
            elif game.state == "gameover":
                # reset (complete reset including upgrades)
                game = Game()
                if MUSIC:
                    try: pygame.mixer.music.set_volume(0.28)
                    except: pass
        elif ev.type == pygame.MOUSEBUTTONUP:
            shooting = False
            touch_pos = None
        elif ev.type == pygame.MOUSEMOTION:
            if pygame.mouse.get_pressed()[0]:
                touch_pos = ev.pos
        elif ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                running = False
            if ev.key == pygame.K_SPACE:
                if game.state == "menu":
                    game.set_difficulty("Normal")
                elif game.state == "playing":
                    shooting = True
            if ev.key == pygame.K_r and game.state == "gameover":
                game = Game()
        elif ev.type == pygame.KEYUP:
            if ev.key == pygame.K_SPACE:
                shooting = False

    # update
    if game.state == "playing":
        # move player toward touch position if available
        if touch_pos:
            mx,my = touch_pos
            if my < PLAY_H:
                game.player.move_toward(mx, my)
        # auto-shoot when holding
        if shooting and game.player.can_shoot():
            new_bs = game.player.shoot()
            game.bullets.extend(new_bs)
        game.update()

    # draw screen
    if game.state == "menu":
        screen.fill((8,12,20))
        draw_text(screen, "SKY DEFENDER (2.5D)", WIDTH//2, HEIGHT//4, BIG, WHITE, center=True)
        draw_text(screen, "Tap a difficulty to start", WIDTH//2, HEIGHT//4 + 54, FONT, WHITE, center=True)
        draw_text(screen, f"Highscore: {game.highscore}", WIDTH//2, HEIGHT//4 + 96, FONT, WHITE, center=True)
        # three buttons
        bw = int(110 * (WIDTH/480)); pad = int(20*(WIDTH/480))
        x0 = WIDTH//2 - int(1.5*bw + pad)
        ry = HEIGHT//2 + 20
        for i,lab in enumerate(["Easy","Normal","Hard"]):
            rx = x0 + i*(bw+pad)
            pygame.draw.rect(screen, (30,30,40), (rx, ry, bw, 56), border_radius=10)
            draw_text(screen, lab, rx + bw//2, ry + 28, BIG, WHITE, center=True)
        draw_text(screen, "Creator: @kawasakl_ninja", WIDTH - 220, HEIGHT - 40)
    elif game.state == "playing":
        game.draw(screen)
    else:  # gameover
        game.draw(screen)
        # overlay
        s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        s.fill((0,0,0,160))
        screen.blit(s, (0,0))
        draw_text(screen, "GAME OVER", WIDTH//2, HEIGHT//3, BIG, WHITE, center=True)
        draw_text(screen, f"Score: {game.score}", WIDTH//2, HEIGHT//3 + 64, FONT, WHITE, center=True)
        draw_text(screen, "Tap to return to menu", WIDTH//2, HEIGHT//3 + 110, FONT, WHITE, center=True)

    pygame.display.flip()

pygame.quit()
sys.exit()