import sys

from direct.showbase.ShowBase import ShowBase
from direct.filter.FilterManager import FilterManager
from direct.interval.IntervalGlobal import LerpFunctionInterval
from panda3d import core
import pman.shim
import json

from .world import World
from .packs import level_packs
from . import ui


class MyFilterManager(FilterManager):
    multisamples = None

    def createBuffer(self, name, xsize, ysize, texgroup, depthbits=1):
        winprops = core.WindowProperties(size=(xsize, ysize))
        props = core.FrameBufferProperties(core.FrameBufferProperties.get_default())
        props.back_buffers = 0
        props.rgb_color = 1
        props.depth_bits = depthbits

        if self.multisamples:
            props.multisamples = self.multisamples

        depthtex, colortex, auxtex0, auxtex1 = texgroup
        buffer = base.graphics_engine.make_output(
            self.win.getPipe(), name, -1,
            props, winprops, core.GraphicsPipe.BF_refuse_window | core.GraphicsPipe.BF_resizeable,
            self.win.getGsg(), self.win)
        if buffer is None:
            return buffer
        if depthtex:
            buffer.add_render_texture(depthtex, core.GraphicsOutput.RTM_bind_or_copy, core.GraphicsOutput.RTP_depth)
        if colortex:
            buffer.add_render_texture(colortex, core.GraphicsOutput.RTM_bind_or_copy, core.GraphicsOutput.RTP_color)
        buffer.set_sort(self.nextsort)
        buffer.disable_clears()
        self.nextsort += 1
        return buffer


class GameApp(ShowBase):
    def __init__(self):
        self.settings = core.load_prc_file(core.Filename.expand_from("$MAIN_DIR/settings.prc"))

        ShowBase.__init__(self, windowType='none')

        # Try opening "gl-version 3 2" window
        props = core.WindowProperties.get_default()
        have_window = False
        try:
            self.open_default_window(props=props)
            have_window = True
        except Exception:
            pass

        if not have_window:
            print("Failed to open window with OpenGL 3.2; falling back to older OpenGL.")
            core.load_prc_file_data("", "gl-version")
            self.open_default_window(props=props)
            print("The window seemed to have opened this time around.")

        gsg = self.win.gsg
        gl_version = (gsg.driver_version_major, gsg.driver_version_minor)
        self.has_fixed_function = gl_version < (3, 2) or \
            gsg.has_extension("GL_ARB_compatibility")

        print("OpenGL version: {0}.{1} ({2})".format(*gl_version, 'compat' if self.has_fixed_function else 'core'))

        # Initialize panda3d-pman
        pman.shim.init(self)

        self.accept('escape', sys.exit)
        self.accept('f12', self.screenshot)
        self.disable_mouse()

        self.camLens.set_far(50)

        # Load in background
        self.set_background_color((0.31, 0.42, 0.53))
        if not self.win.get_fb_properties().srgb_color:
            print("Did not get an sRGB framebuffer.  The game may appear too dark.")

        self.symbol_font = loader.load_font("font/FreeSerif.otf")
        self.symbol_font.set_pixels_per_unit(64)

        self.regular_font = loader.load_font("font/Quicksand-Regular.otf")
        self.regular_font.set_pixels_per_unit(64)

        self.title_font = loader.load_font("font/Quicksand-Light.otf")
        self.title_font.set_pixels_per_unit(128)

        self.icon_fonts = {
            'solid': loader.load_font("font/font-awesome5-solid.otf"),
            'regular': loader.load_font("font/font-awesome5-regular.otf"),
        }
        for font in self.icon_fonts.values():
            font.set_pixels_per_unit(64)

        self.blur_shader = core.Shader.load(core.Shader.SL_GLSL, "shader/blur.vert", "shader/blur.frag")
        self.blur_scale = core.PTA_float([1.0])

        self.blurred_tex = None

        self.quality = None
        screen = ui.Screen("select quality")
        ui.Button(screen, 'sublime', pos=(0.0, 0), command=self.setup_game, extraArgs=[3])
        ui.Button(screen, 'mediocre', pos=(0.0, -0.15), command=self.setup_game, extraArgs=[2])
        ui.Button(screen, 'terrible', pos=(0.0, -0.3), command=self.setup_game, extraArgs=[1])
        self.quality_screen = screen

        screen.show_now()
        self.game_setup = False
        self.have_save = False
        self.blurred = False

    def setup_game(self, quality):
        if self.game_setup:
            return

        self.game_setup = True

        self.quality_screen.hide_now()
        self.quality = quality

        if quality >= 3:
            MyFilterManager.multisamples = 16
            self.render.set_antialias(core.AntialiasAttrib.M_multisample)

            # Increase the quality of all the fonts.
            self.symbol_font.clear()
            self.symbol_font.set_pixels_per_unit(128)

            self.regular_font.clear()
            self.regular_font.set_pixels_per_unit(96)

            self.title_font.clear()
            self.title_font.set_pixels_per_unit(192)
            self.title_font.set_page_size(512, 256)

            for font in self.icon_fonts.values():
                font.clear()
                font.set_pixels_per_unit(96)
                font.set_page_size(512, 256)

        if quality >= 2:
            self.setup_filters()

        if quality >= 2 or not self.has_fixed_function:
            self.lighting_shader = core.Shader.load(core.Shader.SL_GLSL, 'assets/shader/lighting.vert', 'assets/shader/lighting.frag')
        else:
            self.lighting_shader = None

        if quality >= 2:
            # Load skybox
            sky = loader.load_model("gfx/sky.bam")
            sky.reparent_to(self.camera)
            sky.set_scale(10)
            sky.set_bin('background', 0)
            sky.set_depth_write(False)
            sky.set_depth_test(False)
            sky.set_shader_off(1)
            sky.set_compass()
            if self.win.get_fb_properties().srgb_color:
                for tex in sky.find_all_textures():
                    tex.set_format(core.Texture.F_srgb)

        self.world = World()
        self.world.root.reparent_to(self.render)

        num_packs = len(level_packs)
        x = (num_packs - 1) * -0.2

        self.level_buttons = {}

        screen = ui.Screen("level select")
        for pack_name, levels in level_packs:
            while len(levels) < 6:
                levels.append(None)
            panel = ui.Panel(screen, (-0.15, 0.15, -0.25, 0.25), title=pack_name)

            y = 0
            for l, r in (1, 2), (3, 4), (5, 6):
                level_l = levels[l-1]
                level_r = levels[r-1]
                btn_l = ui.LevelButton(panel, l, (-0.05, y), command=self.start_game, extraArgs=[pack_name, l-1], locked=not level_l)
                btn_r = ui.LevelButton(panel, r, (0.05, y), command=self.start_game, extraArgs=[pack_name, r-1], locked=not level_r)
                if level_l:
                    self.level_buttons[level_l] = btn_l
                if level_r:
                    self.level_buttons[level_r] = btn_r
                y -= 0.1

            panel.path.set_x(x)
            x += 0.4

        ui.Button(screen, 'back', pos=(0, -0.5), command=self.show_main)
        self.level_select = screen

        screen = ui.Screen("hexima")
        self.continue_button = ui.Button(screen, '???', pos=(0.0, -0.15*0), command=self.continue_game)
        ui.Button(screen, 'select level', pos=(0.0, -0.15*1), command=self.show_level_select)
        self.fullscreen_button = ui.Button(screen, 'fullscreen', pos=(0.0, -0.15*2), command=self.toggle_fullscreen)
        ui.Button(screen, 'quit', pos=(0.0, -0.15*3), command=self.show_quit)

        self.load_save_state()

        self.main_menu = screen
        screen.show()
        self.current_screen = screen

        self.task_mgr.add(self.process_world)

        self.quit_screen = ui.Screen("quit?")
        ui.Button(self.quit_screen, 'yes, quit', pos=(0, -0.15*0), command=sys.exit)
        ui.Button(self.quit_screen, 'no, stay', pos=(0, -0.15*1), command=self.show_main)

        self.new_game_screen = ui.Screen("erase save?")
        ui.Button(self.new_game_screen, 'yes, erase', pos=(0, -0.15*0), command=self.start_game)
        ui.Button(self.new_game_screen, 'no, cancel', pos=(0, -0.15*1), command=self.show_main)

        self.pause_screen = ui.Screen("paused")
        ui.Button(self.pause_screen, 'continue', pos=(0, -0.15*0), command=self.continue_game)
        ui.Button(self.pause_screen, 'restart level', pos=(0, -0.15*1), command=self.restart_level)
        ui.Button(self.pause_screen, 'skip level', pos=(0, -0.15*2), command=self.skip_level)
        ui.Button(self.pause_screen, 'main menu', pos=(0, -0.15*3), command=self.show_main)

        self.accept('escape', self.show_quit)

    def blur(self):
        if self.blurred:
            return

        self.blurred = True
        LerpFunctionInterval(lambda x: base.blur_scale.set_element(0, x), 0.5, fromData=0.0, toData=1.0).start()

    def unblur(self):
        if not self.blurred:
            return
        self.blurred = False
        LerpFunctionInterval(lambda x: base.blur_scale.set_element(0, x), 0.5, fromData=1.0, toData=0.0).start()

    def show_quit(self):
        self.world.hud.hide()
        self.current_screen.hide()
        self.quit_screen.show()
        self.current_screen = self.quit_screen
        self.blur()
        self.world.player_control.lock()
        self.accept('escape', self.show_main)

    def show_main(self):
        self.world.hud.hide()
        self.current_screen.hide()
        self.main_menu.show()
        self.current_screen = self.main_menu
        self.blur()
        self.world.player_control.lock()
        self.accept('escape', self.show_quit)

    def show_new_game(self):
        self.world.hud.hide()
        self.current_screen.hide()
        self.new_game_screen.show()
        self.current_screen = self.new_game_screen
        self.blur()
        self.world.player_control.lock()
        self.accept('escape', self.show_main)

    def show_level_select(self):
        self.world.hud.hide()
        self.current_screen.hide()
        self.level_select.show()
        self.current_screen = self.level_select
        self.blur()
        self.world.player_control.lock()
        self.accept('escape', self.show_main)

    def show_pause(self):
        self.world.hud.hide()
        self.current_screen.hide()
        self.pause_screen.show()
        self.current_screen = self.pause_screen
        self.blur()
        self.world.player_control.lock()
        self.accept('escape', self.continue_game)

    def start_new_game(self):
        self.erase_save_state()
        self.start_game("one", 1)

    def start_game(self, pack_name, li):
        self.current_screen.hide()
        self.unblur()
        self.accept('escape', self.show_pause)

        pack = dict(level_packs)[pack_name]
        if li >= len(pack):
            return

        level = pack[li]
        if not level:
            return

        self.world.load_level(level)
        self.world.next_levels = pack[li + 1:]

    def continue_game(self):
        if not self.world.level:
            if self.next_level:
                self.start_game(*self.next_level)
            else:
                # We've already won, no level hasn't been gotten yet.
                self.show_level_select()
        else:
            self.current_screen.hide()
            self.unblur()
            self.load_save_state()
            self.accept('escape', self.show_pause)

            self.world.player_control.unlock()
            self.world.hud.show()

    def restart_level(self):
        self.current_screen.hide()
        self.unblur()
        self.world.reload_level()
        self.accept('escape', self.show_pause)

    def skip_level(self):
        self.current_screen.hide()
        self.unblur()
        self.world.load_next_level()
        self.accept('escape', self.show_pause)

    def erase_save_state(self):
        print("Erasing save state")
        self.have_save = False
        fp = open('save.json', 'w')
        fp.write('{}')
        fp.close()
        self.update_level_overview({})

    def toggle_fullscreen(self):
        if not self.win.get_properties().fullscreen:
            print("Switching to fullscreen mode")
            size = self.pipe.get_display_width(), self.pipe.get_display_height()
            self.win.request_properties(core.WindowProperties(fullscreen=True, size=size))
            self.fullscreen_button.set_text('windowed')
        else:
            print("Switching to windowed mode")
            size = core.WindowProperties.get_default().size
            self.win.request_properties(core.WindowProperties(fullscreen=False, size=size, origin=(-2, -2)))
            self.fullscreen_button.set_text('fullscreen')

    def load_save_state(self):
        try:
            data = json.load(open('save.json', 'r'))
        except Exception as ex:
            print("Failed to load saves: {0}".format(ex))
            data = {}

        self.update_level_overview(data)

    def update_save_state(self, level, score, star=False, par=None):
        try:
            data = json.load(open('save.json', 'r'))
        except Exception as ex:
            print("Failed to load saves: {0}".format(ex))
            data = {}

        if 'levels' not in data:
            data['levels'] = {}

        if level not in data['levels']:
            state = {'best': score, 'star': star}
            data['levels'][level] = state
        else:
            state = data['levels'][level]
            state['best'] = min(state.get('best', score), score)
            if score <= state['best']:
                # This is our best score, if we didn't get a star, or the par
                # changed, ignore whether we previously had a star.
                state['star'] = star
            else:
                state['star'] = state.get('star', False) or star

        if par is not None:
            state['par'] = par

        self.update_level_overview(data)

        try:
            json.dump(data, open('save.json', 'w'), indent=4, sort_keys=True)
        except Exception as ex:
            print("Failed to write saves: {0}".format(ex))

    def update_level_overview(self, data):
        level_states = data.get('levels', {})

        self.have_save = (len(level_states) > 0)
        if self.have_save:
            self.continue_button.set_text('continue')
        else:
            self.continue_button.set_text('new game')
        next_level = None

        for pack_name, levels in level_packs:
            for li, level in enumerate(levels):
                button = self.level_buttons.get(level, None)
                if button:
                    state = level_states.get(level, {})
                    if state.get('star'):
                        button.set_badge('', style='solid', color=(1, 0.8, 0.3, 1))
                    elif state.get('best'):
                        button.set_badge('', style='solid', color=(0.2, 0.8, 0.1, 1))
                    elif next_level is None:
                        next_level = (pack_name, li)

        self.next_level = next_level

    def setup_filters(self):
        self.filters = MyFilterManager(base.win, base.cam)
        self.scene_tex = core.Texture()
        self.scene_tex.set_wrap_u(core.Texture.WM_clamp)
        self.scene_tex.set_wrap_v(core.Texture.WM_clamp)
        self.quad = self.filters.render_scene_into(colortex=self.scene_tex)
        self.quad.clear_color()

        if not self.quad:
            return

        prev_tex = self.scene_tex

        if self.quality >= 3:
            intermediate_tex = core.Texture()
            intermediate_tex.set_minfilter(core.Texture.FT_linear)
            intermediate_tex.set_magfilter(core.Texture.FT_linear)
            intermediate_tex.set_wrap_u(core.Texture.WM_clamp)
            intermediate_tex.set_wrap_v(core.Texture.WM_clamp)
            intermediate_quad = self.filters.render_quad_into("blur-x", colortex=intermediate_tex)
            intermediate_quad.set_shader_input("image", prev_tex)
            intermediate_quad.set_shader_input("direction", (2, 0))
            intermediate_quad.set_shader_input("scale", self.blur_scale)
            intermediate_quad.set_shader(self.blur_shader)
            prev_tex = intermediate_tex

            intermediate_tex = core.Texture()
            intermediate_tex.set_minfilter(core.Texture.FT_linear)
            intermediate_tex.set_magfilter(core.Texture.FT_linear)
            intermediate_tex.set_wrap_u(core.Texture.WM_clamp)
            intermediate_tex.set_wrap_v(core.Texture.WM_clamp)
            intermediate_quad = self.filters.render_quad_into("blur-y", colortex=intermediate_tex)
            intermediate_quad.set_shader_input("image", prev_tex)
            intermediate_quad.set_shader_input("direction", (0, 2))
            intermediate_quad.set_shader_input("scale", self.blur_scale)
            intermediate_quad.set_shader(self.blur_shader)
            prev_tex = intermediate_tex

        intermediate_tex = core.Texture()
        intermediate_tex.set_minfilter(core.Texture.FT_linear)
        intermediate_tex.set_magfilter(core.Texture.FT_linear)
        intermediate_tex.set_wrap_u(core.Texture.WM_clamp)
        intermediate_tex.set_wrap_v(core.Texture.WM_clamp)
        intermediate_quad = self.filters.render_quad_into("blur-y", colortex=intermediate_tex)
        intermediate_quad.set_shader_input("image", prev_tex)
        intermediate_quad.set_shader_input("direction", (0, 4))
        intermediate_quad.set_shader_input("scale", self.blur_scale)
        intermediate_quad.set_shader(self.blur_shader)
        prev_tex = intermediate_tex

        self.blurred_tex = prev_tex

    def __del__(self):
        core.unload_prc_file(self.settings)

    def process_world(self, task):
        self.world.process(globalClock.dt)
        return task.cont
