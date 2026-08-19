with open('RadialMenu.tab/RadialMenu.panel/ToggleRadialMenu.pushbutton/script.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

with open('hook_code.py', 'r', encoding='utf-8') as f:
    hook_code = f.read()

insert_idx = -1
for i, line in enumerate(lines):
    if 'def on_search_changed(self, sender, args):' in line and i > 5000:
        insert_idx = i
        break

if insert_idx != -1:
    lines.insert(insert_idx, hook_code + '\n\n')

# now replace lines directly instead of strings
for i, line in enumerate(lines):
    if 'self._move_mode_active = True' in line and 'def on_core_move_clicked' in ''.join(lines[i-15:i]):
        # insert subscribe
        sub = '''            try:
                from System.Windows.Input import InputManager, NotifyInputEventHandler
                if not hasattr(self, '_input_delegate') or not self._input_delegate:
                    self._input_delegate = NotifyInputEventHandler(self.on_input_manager_pre_notify)
                    InputManager.Current.PostNotifyInput += self._input_delegate
                    log_debug('Subscribed to global WPF InputManager events for Ribbon drag-and-drop.')
            except Exception as ad_ex:
                log_debug('Failed to subscribe to InputManager events: ' + str(ad_ex))\n'''
        lines.insert(i+1, sub)
        break

for i, line in enumerate(lines):
    if 'self._move_mode_active = False' in line and 'def on_core_pool_clicked' in ''.join(lines[i-15:i]):
        unsub = '''            try:
                from System.Windows.Input import InputManager
                if hasattr(self, '_input_delegate') and self._input_delegate:
                    InputManager.Current.PostNotifyInput -= self._input_delegate
                    self._input_delegate = None
                    log_debug('Unsubscribed from global WPF InputManager events.')
            except Exception as ad_ex:
                log_debug('Failed to unsubscribe from InputManager events: ' + str(ad_ex))\n'''
        lines.insert(i+1, unsub)
        break

for i, line in enumerate(lines):
    if 'self._move_mode_active = False' in line and 'def on_core_appearance_clicked' in ''.join(lines[i-15:i]):
        unsub = '''            try:
                from System.Windows.Input import InputManager
                if hasattr(self, '_input_delegate') and self._input_delegate:
                    InputManager.Current.PostNotifyInput -= self._input_delegate
                    self._input_delegate = None
                    log_debug('Unsubscribed from global WPF InputManager events.')
            except Exception as ad_ex:
                log_debug('Failed to unsubscribe from InputManager events: ' + str(ad_ex))\n'''
        lines.insert(i+1, unsub)
        break

for i, line in enumerate(lines):
    if 'self._move_mode_active = False' in line and 'def exit_customizer_mode' in ''.join(lines[i-15:i]):
        unsub = '''            try:
                from System.Windows.Input import InputManager
                if hasattr(self, '_input_delegate') and self._input_delegate:
                    InputManager.Current.PostNotifyInput -= self._input_delegate
                    self._input_delegate = None
                    log_debug('Unsubscribed from global WPF InputManager events.')
            except Exception as ad_ex:
                log_debug('Failed to unsubscribe from InputManager events: ' + str(ad_ex))\n'''
        lines.insert(i+1, unsub)
        break

for i, line in enumerate(lines):
    if 'log_debug("RadialMenuWindow closed, _active_window cleared.")' in line:
        unsub = '''        try:
            from System.Windows.Input import InputManager
            if hasattr(self, '_input_delegate') and self._input_delegate:
                InputManager.Current.PostNotifyInput -= self._input_delegate
                self._input_delegate = None
                log_debug('Unsubscribed from global WPF InputManager events on window closing.')
        except Exception as ad_ex:
            log_debug('Failed to unsubscribe from InputManager events: ' + str(ad_ex))\n'''
        lines.insert(i+1, unsub)
        break

with open('RadialMenu.tab/RadialMenu.panel/ToggleRadialMenu.pushbutton/script.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
