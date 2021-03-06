__all__ = ['Panel', 'Button']

from direct.gui.DirectFrame import DirectFrame
from direct.gui.DirectButton import DirectButton
from direct.gui.OnscreenText import OnscreenText
import direct.gui.DirectGuiGlobals as DGG
from direct.interval.IntervalGlobal import LerpFunctionInterval, Func, Sequence, Parallel
from panda3d import core
from random import random


BORDER_WIDTH = 0.005
UI_COLOR = (1, 1, 1, 1)


def generate_border(path, frame):
    cm = core.CardMaker("border")
    cm.set_frame(frame[0] - BORDER_WIDTH, frame[0], frame[2] - BORDER_WIDTH, frame[3] + BORDER_WIDTH)
    border = path.attach_new_node(cm.generate())
    border.set_shader_off(1)
    border.set_color_scale_off(1)

    cm.set_frame(frame[1], frame[1] + BORDER_WIDTH, frame[2] - BORDER_WIDTH, frame[3] + BORDER_WIDTH)
    border = path.attach_new_node(cm.generate())
    border.set_shader_off(1)
    border.set_color_scale_off(1)

    cm.set_frame(frame[0] - BORDER_WIDTH, frame[1] + BORDER_WIDTH, frame[2] - BORDER_WIDTH, frame[2])
    border = path.attach_new_node(cm.generate())
    border.set_shader_off(1)
    border.set_color_scale_off(1)

    cm.set_frame(frame[0] - BORDER_WIDTH, frame[1] + BORDER_WIDTH, frame[3], frame[3] + BORDER_WIDTH)
    border = path.attach_new_node(cm.generate())
    border.set_shader_off(1)
    border.set_color_scale_off(1)


class Panel:
    def __init__(self, parent, frame=None, pos=(0, 0), anchor=None, title=""):
        text_pos = ((frame[1] + frame[0]) * 0.5, frame[3] - 0.1)
        self.path = DirectFrame(frameSize=frame, relief=None, parent=parent.path, text=title, text_scale=0.09, text_align=core.TextNode.A_center, text_fg=UI_COLOR, text_pos=text_pos, text_font=base.regular_font)
        generate_border(self.path, frame)

        #if anchor is None:
        #    self.path.reparent_to(base.aspect2d)
        #else:
        #    self.path.reparent_to(getattr(base, 'a2d' + anchor))

        #self.path.set_shader(base.blur_shader)
        #self.path.set_shader_input("image", base.blurred_tex)
        #self.path.set_shader_input("direction", (1, 1))
        #self.path.set_color_scale((0.8, 0.8, 0.8, 1.0))


class LevelButton:
    font = None

    def __init__(self, parent, number=1, pos=(0, 0), command=None, extraArgs=[], locked=False):
        text = '⚀⚁⚂⚃⚄⚅'[number - 1]
        self.path = DirectButton(parent=parent.path, text_fg=UI_COLOR, text_font=base.symbol_font, relief=None, text=text, scale=0.07, text_scale=2, pos=(pos[0], 0, pos[1]), command=command, extraArgs=extraArgs)

        #text = ''[number - 1]
        #self.path = DirectButton(parent=parent.path, text_fg=UI_COLOR, text_font=self.font, relief=None, text=text, scale=0.07, pos=(pos[0], 0, pos[1]))
        self.path.set_shader_off(1)
        self.path.set_color_scale_off(1)

        self.badge = None
        if locked:
            self.path.set_color_scale((1, 1, 1, 0.5))
            self.set_badge('')

    def set_badge(self, icon, style='solid', color=UI_COLOR):
        if self.badge:
            self.badge.destroy()

        font = base.icon_fonts[style]
        self.badge = OnscreenText(parent=self.path, text=icon, font=font, scale=0.6, pos=(0.28, -0.08), fg=UI_COLOR)
        self.badge.set_color_scale(color, 2)


class HUD:
    def __init__(self, anchor=None):
        self.anchors = {
            'top-left': base.a2dTopLeft.attach_new_node('hud-tl'),
            'top-center': base.a2dTopCenter.attach_new_node('hud-tc'),
            'top-right': base.a2dTopRight.attach_new_node('hud-tr'),
            'bottom-left': base.a2dBottomLeft.attach_new_node('hud-bl'),
            'bottom-right': base.a2dBottomRight.attach_new_node('hud-br'),
        }
        for path in self.anchors.values():
            path.hide()
            path.set_color_scale((1, 1, 1, 0))
        self.visible = False

    def _child_item_added(self, item):
        pass

    def show(self):
        if self.visible:
            return
        self.visible = True
        duration = 0.5
        for path in self.anchors.values():
            path.show()
            path.colorScaleInterval(duration, (1, 1, 1, 1)).start()

    def hide(self):
        if not self.visible:
            return
        self.visible = False
        duration = 0.5
        for path in self.anchors.values():
            Sequence(
                path.colorScaleInterval(duration, (1, 1, 1, 0)),
                Func(path.hide),
            ).start()


class Button:
    def __init__(self, parent, text="", pos=(0, 0), size=(0.4, 0.2), command=None, extraArgs=[], icon=None, icon_style='solid', disabled=False, anchor=None):
        parent_path = parent.path if anchor is None else parent.anchors[anchor]

        #frame = (-size[0] * 0.5, size[0] * 0.5, -size[1] * 0.5, size[1] * 0.5)
        frame = (-0.15, 0.25 if icon else 0.15, -0.03, 0.08)
        self.path = DirectButton(parent=parent_path, text_fg=UI_COLOR, relief=None, frameSize=frame, text=text, text_scale=0.09, pos=(pos[0], 0, pos[1]), command=command, extraArgs=extraArgs)
        #generate_border(self.path, frame)

        if disabled:
            self.path['state'] = DGG.DISABLED

        if icon is not None:
            self.icon_pivot = self.path.attach_new_node('pivot')
            self.icon_pivot.set_pos(-0.1, 0, 0.025)
            font = base.icon_fonts[icon_style]
            text = OnscreenText(parent=self.icon_pivot, text=icon, fg=(1, 1, 1, 1), font=font, align=core.TextNode.A_center, scale=0.07, pos=(-0.002, -0.025))
        else:
            self.icon_pivot = None

        self.path.bind('enter-', self.on_focus)
        self.path.bind('exit-', self.on_blur)
        self.path.bind('fin-', self.on_focus)
        self.path.bind('fout-', self.on_blur)

        self.path.set_shader_off(1)

        self.path.set_color_scale((1, 1, 1, 0.6))

        parent._child_item_added(self.path)

    def set_text(self, text):
        self.path['text'] = text

    def focus(self):
        self.path.guiItem.set_focus(True)

    def enable(self):
        self.path['state'] = DGG.NORMAL

    def disable(self):
        self.path['state'] = DGG.DISABLED

    def on_focus(self, param=None):
        if self.icon_pivot is not None:
            self.icon_pivot.hprInterval(0.2, (0, 0, 360), blendType='easeInOut').start()

        self.path.colorScaleInterval(0.2, (1, 1, 1, 1), blendType='easeInOut').start()
        self.path.guiItem.set_state(2)

    def on_blur(self, param=None):
        if self.icon_pivot is not None:
            self.icon_pivot.hprInterval(0.2, (0, 0, 0), blendType='easeInOut').start()

        self.path.colorScaleInterval(0.2, (1, 1, 1, 0.6), blendType='easeInOut').start()
        self.path.guiItem.set_state(0)


class ToggleButton(Button):
    def __init__(self, parent, state, off_text, on_text, pos=(0, 0), size=(0.4, 0.2), command=None, off_icon=None, on_icon=None, icon_style='solid', disabled=False, anchor=None):
        self.state = state
        self._command = command
        self._text = (off_text, on_text)
        self._icon = (off_icon, on_icon)
        Button.__init__(self, parent, pos=pos, size=size, command=self.toggle, extraArgs=[], icon=off_icon, icon_style=icon_style, disabled=disabled, anchor=anchor)
        self.set_text(self._text[state])
        #self.set_icon(self._icon[state])

    def toggle(self):
        state = not self.state
        self.state = state
        if self._command:
            self._command(state)
        self.set_text(self._text[state])
        #self.set_icon(self._icon[state])


class Icon:
    def __init__(self, parent, icon='', pos=(0, 0), style='solid', anchor=None):
        parent_path = parent.path if anchor is None else parent.anchors[anchor]
        self.pos = pos

        self.path = parent_path.attach_new_node('icon')
        self.path.set_color_scale((1, 1, 1, 1))
        self.path.set_pos(pos[0], 0, pos[1])

        self.icon = None
        if icon:
            self.set(icon, style=style)

    def set(self, icon, style='solid'):
        old_icon = self.icon
        if old_icon:
            self.clear()
        font = base.icon_fonts[style]
        self.icon = OnscreenText(parent=self.path, text=icon, fg=(1, 1, 1, 1), font=font, align=core.TextNode.A_center, scale=0.12)

    def clear(self):
        old_icon = self.icon
        if old_icon:
            Sequence(
                old_icon.colorScaleInterval(0.2, (1, 1, 1, 0)),
                Func(old_icon.destroy),
            ).start()

    def flash(self, color):
        if self.icon:
            self.icon.set_color_scale(color)
            self.icon.colorScaleInterval(1.5, (1, 1, 1, 1)).start()


class Indicator:
    def __init__(self, parent, value=0, pos=(0, 0), size=(0.4, 0.2), icon=None, icon_style='solid', anchor=None):
        parent_path = parent.path if anchor is None else parent.anchors[anchor]

        self.value = value

        self.path = OnscreenText(parent=parent_path, fg=UI_COLOR, text=str(value), scale=0.09, pos=pos, align=core.TextNode.A_right)
        self.path.set_color_scale((1, 1, 1, 0.8))

        self.icon = None
        self.icon_pos = (pos[0] + 0.07, pos[1] + 0.01)
        if icon:
            self.set_icon(icon, style=icon_style)

    def inc_value(self):
        new_value = self.value + 1
        self.set_value(new_value)
        return new_value

    def set_value(self, value):
        self.value = value
        self.path['text'] = str(value)

    def set_icon(self, icon, style='solid'):
        old_icon = self.icon
        if old_icon:
            self.clear_icon()
        font = base.icon_fonts[style]
        self.icon = OnscreenText(parent=self.path, text=icon, fg=(1, 1, 1, 1), font=font, align=core.TextNode.A_center, scale=0.07, pos=self.icon_pos)

    def clear_icon(self):
        old_icon = self.icon
        if old_icon:
            Sequence(
                old_icon.colorScaleInterval(1.0, (1, 1, 1, 0)),
                Func(old_icon.destroy),
            ).start()

class Screen:
    def __init__(self, title=""):
        self.path = OnscreenText(text=title, scale=0.2, pos=(0, 0.5), fg=UI_COLOR, font=base.title_font)

        if base.blurred_tex:
            cm = core.CardMaker("card")
            cm.set_frame_fullscreen_quad()
            card = render2d.attach_new_node(cm.generate())
            card.set_shader(base.blur_shader)
            card.set_shader_input("image", base.blurred_tex)
            card.set_shader_input("direction", (4, 0))
            card.set_shader_input("scale", base.blur_scale)
            card.set_transparency(1)
            self.blur_card = card
        else:
            self.blur_card = core.NodePath("")

        cm = core.CardMaker("card")
        cm.set_frame_fullscreen_quad()
        card = render2d.attach_new_node(cm.generate())

        if base.quality is None:
            card.set_color(core.LColor(0, 0, 0, 0.5))
        else:
            card.set_color(core.LColor(0, 0, 0, 1))

        card.set_transparency(1)
        card.set_bin('fixed', 40)
        self.fade_card = card

        # Start hidden
        self.hide_now()

        self._first_item = None
        self._prev_item = None

    def _child_item_added(self, item):
        # Set up keyboard navigation.
        item.guiItem.add_click_button('enter')
        item.guiItem.add_click_button('space')
        item.guiItem.add_click_button('face_a')
        item.guiItem.add_click_button('face_x')

        item.bind('enter-', lambda p: item.guiItem.set_focus(True))
        item.unbind('exit-')
        item.bind('press-enter-', item.commandFunc)
        item.bind('press-space-', item.commandFunc)
        item.bind('press-face_a-', item.commandFunc)
        item.bind('press-face_x-', item.commandFunc)

        prev = self._prev_item
        if prev is not None:
            prev.bind('press-arrow_down-', lambda p: item.guiItem.set_focus(True))
            prev.bind('press-dpad_down-', lambda p: item.guiItem.set_focus(True))
            prev.bind('press-lstick_down-', lambda p: item.guiItem.set_focus(True))
            item.bind('press-arrow_up-', lambda p: prev.guiItem.set_focus(True))
            item.bind('press-dpad_up-', lambda p: prev.guiItem.set_focus(True))
            item.bind('press-lstick_up-', lambda p: prev.guiItem.set_focus(True))

        sound = item['clickSound']
        if sound:
            item.guiItem.set_sound('press-enter-' + item.guiId, sound)
            item.guiItem.set_sound('press-space-' + item.guiId, sound)
            item.guiItem.set_sound('press-face_a-' + item.guiId, sound)
            item.guiItem.set_sound('press-face_x-' + item.guiId, sound)

        sound = item['rolloverSound']
        if sound:
            item.guiItem.set_sound('press-arrow_up-' + item.guiId, sound)
            item.guiItem.set_sound('press-dpad_up-' + item.guiId, sound)
            item.guiItem.set_sound('press-lstick_up-' + item.guiId, sound)
            item.guiItem.set_sound('press-arrow_down-' + item.guiId, sound)
            item.guiItem.set_sound('press-dpad_down-' + item.guiId, sound)
            item.guiItem.set_sound('press-lstick_down-' + item.guiId, sound)

        self._prev_item = item
        if self._first_item is None:
            self._first_item = item

    def focus(self):
        if self._first_item is not None:
            self._first_item.guiItem.set_focus(True)

    def show(self):
        if self.visible:
            return
        self.visible = True
        duration = 0.5
        Sequence(
            Func(self.blur_card.show),
            Func(self.fade_card.show),
            Parallel(
                LerpFunctionInterval(lambda x: self.blur_card.set_alpha_scale(x), duration, fromData=0.0, toData=1.0),
                LerpFunctionInterval(lambda x: self.fade_card.set_alpha_scale(x), duration, fromData=0.0, toData=0.5),
            ),
            Func(self.path.show),
            Func(self.focus),
        ).start()

    def hide(self):
        if not self.visible:
            return
        self.visible = False
        duration = 0.5
        Sequence(
            Parallel(
                LerpFunctionInterval(lambda x: self.blur_card.set_alpha_scale(x), duration, toData=0.0, fromData=1.0),
                LerpFunctionInterval(lambda x: self.fade_card.set_alpha_scale(x), duration, toData=0.0, fromData=0.5),
            ),
            Func(self.blur_card.hide),
            Func(self.fade_card.hide),
        ).start()
        self.path.hide()

    def show_now(self):
        self.fade_card.set_alpha_scale(1)
        self.blur_card.set_alpha_scale(1)
        self.blur_card.show()
        self.fade_card.show()
        self.path.show()
        self.focus()
        self.visible = True

    def hide_now(self):
        self.fade_card.set_alpha_scale(0)
        self.blur_card.set_alpha_scale(0)
        self.blur_card.hide()
        self.fade_card.hide()
        self.path.hide()
        self.visible = False
