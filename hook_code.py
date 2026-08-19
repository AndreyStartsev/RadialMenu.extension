
    def on_input_manager_pre_notify(self, sender, args):
        try:
            if not getattr(self, 'customizer_mode', False) or not getattr(self, '_move_mode_active', False):
                return
            if not args or not args.StagingItem or not args.StagingItem.Input:
                return
            e = args.StagingItem.Input
            
            from System.Windows.Input import MouseButtonEventArgs, MouseEventArgs, MouseButtonState, MouseButton
            import System.Windows.Media as media
            from System.Windows import LogicalTreeHelper, FrameworkElement, FrameworkContentElement
            
            # Check for mouse down
            if isinstance(e, MouseButtonEventArgs) and e.RoutedEvent and e.RoutedEvent.Name == 'PreviewMouseDown':
                if e.ChangedButton == MouseButton.Left:
                    self._ribbon_drag_start = System.Windows.Input.Mouse.GetPosition(None)
                    self._ribbon_dragged_item = None
                    
                    dep = e.OriginalSource
                    best_match = None
                    curr = dep
                    visited = set()
                    depth = 0
                    
                    while curr is not None and depth < 20:
                        depth += 1
                        try:
                            curr_hash = getattr(curr, 'GetHashCode', lambda: id(curr))()
                            if curr_hash in visited:
                                break
                            visited.add(curr_hash)
                            
                            candidates = []
                            if hasattr(curr, 'DataContext') and curr.DataContext:
                                candidates.append(curr.DataContext)
                            if hasattr(curr, 'Item') and curr.Item:
                                candidates.append(curr.Item)
                            if hasattr(curr, 'Source') and curr.Source:
                                candidates.append(curr.Source)
                            candidates.append(curr)
                            
                            for candidate in candidates:
                                if not candidate:
                                    continue
                                c_type = candidate.GetType()
                                c_type_name = c_type.FullName or c_type.Name or ''
                                c_ns = c_type.Namespace or ''
                                
                                c_id = getattr(candidate, 'Id', None) or getattr(candidate, 'CommandId', None) or getattr(candidate, 'Name', None)
                                if c_id and str(c_id).strip():
                                    c_id_str = str(c_id).strip()
                                    is_pulldown = (
                                        'RibbonSplitButton' in c_type_name 
                                        or 'RibbonListButton' in c_type_name 
                                        or 'RibbonGallery' in c_type_name
                                        or 'RibbonMenu' in c_type_name
                                    )
                                    is_btn = (
                                        'RibbonButton' in c_type_name 
                                        or 'RibbonCommandItem' in c_type_name 
                                        or 'RibbonItem' in c_type_name
                                        or 'RibbonToggleButton' in c_type_name
                                        or 'RibbonRadioButton' in c_type_name
                                        or 'RibbonMenuItem' in c_type_name
                                        or 'RibbonCombo' in c_type_name
                                        or 'RibbonTextBox' in c_type_name
                                        or 'Button' in c_type_name
                                        or 'Item' in c_type_name
                                        or 'Autodesk.Windows' in c_ns
                                        or c_id_str.startswith('ID_')
                                        or c_id_str.startswith('CustomCtrl')
                                    )
                                    if is_btn or is_pulldown:
                                        if best_match is None:
                                            best_match = candidate
                            if best_match:
                                break
                                
                            parent = None
                            if isinstance(curr, media.Visual):
                                try:
                                    parent = media.VisualTreeHelper.GetParent(curr)
                                except:
                                    pass
                            if not parent:
                                try:
                                    if isinstance(curr, FrameworkElement) or isinstance(curr, FrameworkContentElement):
                                        parent = curr.Parent or getattr(curr, 'TemplatedParent', None)
                                    if not parent:
                                        parent = LogicalTreeHelper.GetParent(curr)
                                except:
                                    pass
                            curr = parent
                        except Exception as walk_ex:
                            break
                            
                    if best_match:
                        self._ribbon_dragged_item = best_match
                        
            # Check for mouse move
            elif isinstance(e, MouseEventArgs) and e.RoutedEvent and e.RoutedEvent.Name == 'PreviewMouseMove':
                if not getattr(self, '_ribbon_dragged_item', None):
                    return
                if e.LeftButton != MouseButtonState.Pressed:
                    self._ribbon_dragged_item = None
                    return
                    
                pos = System.Windows.Input.Mouse.GetPosition(None)
                start_pos = getattr(self, '_ribbon_drag_start', None)
                if not start_pos:
                    return
                    
                from System.Windows import SystemParameters
                diff_x = abs(pos.X - start_pos.X)
                diff_y = abs(pos.Y - start_pos.Y)
                
                if diff_x > SystemParameters.MinimumHorizontalDragDistance or diff_y > SystemParameters.MinimumVerticalDragDistance:
                    item = self._ribbon_dragged_item
                    self._ribbon_dragged_item = None
                    
                    item_id = getattr(item, 'Id', None) or getattr(item, 'CommandId', None) or getattr(item, 'Name', None)
                    if not item_id:
                        return
                    item_id = str(item_id).strip()
                    e.Handled = True
                    
                    item_text = (getattr(item, 'Text', None) or getattr(item, 'Name', None) or getattr(item, 'Title', None) or getattr(item, 'ToolTip', None) or item_id)
                    try:
                        item_name = str(item_text).replace('\n', ' ').replace('\r', ' ').strip()
                    except:
                        item_name = 'Command'
                    
                    is_pyrevit = 'customctrl_%customctrl_%' in item_id.lower()
                    pyrevit_unique_id = ''
                    
                    if is_pyrevit:
                        if hasattr(self, '_all_commands'):
                            id_lower = item_id.lower()
                            for cmd in self._all_commands:
                                p_uid = cmd.get('unique_id', '')
                                if p_uid.lower() in id_lower or p_uid.lower().replace('_', '') in id_lower.replace('%', '').replace('_', ''):
                                    pyrevit_unique_id = p_uid
                                    break
                        if not pyrevit_unique_id:
                            pyrevit_unique_id = item_id
                    
                    def save_item_icon(r_item):
                        if not r_item:
                            return ''
                        r_id = getattr(r_item, 'Id', None) or getattr(r_item, 'CommandId', None) or getattr(r_item, 'Name', None)
                        if not r_id:
                            return ''
                        r_id_str = str(r_id).strip()
                        safe_fn = ''.join([c for c in r_id_str if c.isalnum() or c in ('_', '-')]).strip()
                        if not safe_fn:
                            return ''
                        import os
                        icons_dir = self._config_data.get('settings', {}).get('custom_icons_dir', '')
                        if not icons_dir:
                            import tempfile
                            icons_dir = os.path.join(tempfile.gettempdir(), 'RadialMenuIcons')
                        if not os.path.exists(icons_dir):
                            try: os.makedirs(icons_dir)
                            except: pass
                        suffix = '.png'
                        file_path = os.path.join(icons_dir, safe_fn + suffix)
                        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
                            img = getattr(r_item, 'LargeImage', None) or getattr(r_item, 'Image', None) or getattr(r_item, 'SmallImage', None)
                            if img:
                                try:
                                    import clr
                                    clr.AddReference('PresentationCore')
                                    from System.Windows.Media.Imaging import PngBitmapEncoder
                                    from System.IO import FileMode, FileAccess, FileStream
                                    from System.Windows.Media.Imaging import BitmapFrame
                                    encoder = PngBitmapEncoder()
                                    encoder.Frames.Add(BitmapFrame.Create(img))
                                    with FileStream(file_path, FileMode.Create, FileAccess.Write) as stream:
                                        encoder.Save(stream)
                                except:
                                    pass
                        return file_path if os.path.exists(file_path) else ''

                    is_pulldown = False
                    ctx_type_name = item.GetType().Name
                    if 'RibbonListButton' in ctx_type_name or 'RibbonSplitButton' in ctx_type_name or 'RibbonGallery' in ctx_type_name or 'RibbonMenu' in ctx_type_name:
                        if hasattr(item, 'Items') and item.Items and len(list(item.Items)) > 0:
                            is_pulldown = True
                        
                    children_list = []
                    if is_pulldown:
                        try:
                            if hasattr(item, 'Items') and item.Items:
                                for child in item.Items:
                                    child_id = getattr(child, 'Id', None) or getattr(child, 'CommandId', None) or getattr(child, 'Name', None)
                                    if child_id:
                                        child_text = getattr(child, 'Text', '') or getattr(child, 'Name', '') or 'Command'
                                        child_name = str(child_text).replace('\n', ' ').replace('\r', ' ').strip()
                                        child_icon = save_item_icon(child)
                                        children_list.append({
                                            'name': child_name,
                                            'unique_id': str(child_id),
                                            'icon_path': child_icon
                                        })
                        except:
                            pass
                        
                    cmd_type = 'pyrevit' if is_pyrevit else 'built_in'
                    cmd_value = pyrevit_unique_id if is_pyrevit else item_id
                    icon_path = save_item_icon(item)
                            
                    import json
                    cmd_dict = {
                        'name': item_name,
                        'unique_id': cmd_value,
                        'extension': 'pyRevit' if is_pyrevit else 'Revit Built-in',
                        'icon_path': icon_path,
                        'is_pulldown': is_pulldown,
                        'children': children_list
                    }
                    cmd_json = json.dumps(cmd_dict)
                    
                    from System import Action
                    def run_drag_drop():
                        try:
                            import System.Windows
                            drag_data = System.Windows.DataObject('PyRevitCommandJSON', cmd_json)
                            System.Windows.DragDrop.DoDragDrop(self, drag_data, System.Windows.DragDropEffects.Copy)
                        except:
                            pass
                        finally:
                            self.clear_gap()
                            try: self.hide_drag_preview()
                            except: pass
                            
                    self._menu_drag_delegate = Action(run_drag_drop)
                    self.Dispatcher.BeginInvoke(self._menu_drag_delegate)
                    
        except Exception as ex:
            pass
