bl_info = {
    "name": "WeightR2",
    "author": "r2detta",
    "version": (1, 3, 10),
    "blender": (4, 5, 0),
    "location": "View3D > Sidebar > WeightR2",
    "description": "Vertex Group Weight Collections and Selected Vertex Weights Viewer",
    "category": "Object",
}

import bpy
import bmesh
from bpy.types import Panel, Operator, PropertyGroup, UIList
from bpy.props import (
    StringProperty,
    IntProperty,
    FloatProperty,
    CollectionProperty,
    PointerProperty,
)


class WEIGHTR2_UL_vertex_groups(UIList):
    """Vertex gruplarını Properties panelindeki gibi liste olarak gösterir."""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            layout.prop(item, "name", text="", emboss=False, icon="GROUP_VERTEX")
        elif self.layout_type in {"GRID"}:
            layout.alignment = "CENTER"
            layout.prop(item, "name", text="", emboss=False, icon="GROUP_VERTEX")


class WeightCollectionGroupItem(PropertyGroup):
    group_name: StringProperty(
        name="Vertex Group",
        description="Name of the vertex group in this collection",
        default="",
    )


class WeightCollectionItem(PropertyGroup):
    name: StringProperty(
        name="Name",
        description="Name of this weight collection",
        default="Collection",
    )

    groups: CollectionProperty(
        name="Groups",
        description="Vertex groups contained in this collection",
        type=WeightCollectionGroupItem,
    )

    active_group_index: IntProperty(
        name="Active Group Index",
        description="Active group index inside this collection",
        default=-1,
    )


class WeightCollectionsProperties(PropertyGroup):
    collections: CollectionProperty(
        name="Collections",
        description="Weight collections for this object",
        type=WeightCollectionItem,
    )

    active_collection_index: IntProperty(
        name="Active Collection",
        description="Active weight collection index",
        default=-1,
    )


class OBJECT_OT_weight_collection_add(Operator):
    """Aktif objeye yeni bir weight collection ekler"""

    bl_idname = "object.weight_collection_add"
    bl_label = "Add Weight Collection"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.type == 'MESH'

    def execute(self, context):
        obj = context.object
        props = obj.weight_collections_props

        new_item = props.collections.add()

        base_name = "Collection"
        existing_names = {c.name for c in props.collections}
        name = base_name
        index = 1
        while name in existing_names:
            index += 1
            name = f"{base_name}.{index:03d}"

        new_item.name = name

        props.active_collection_index = len(props.collections) - 1

        return {'FINISHED'}


class OBJECT_OT_weight_collection_remove(Operator):
    """Seçili weight collection'ı siler"""

    bl_idname = "object.weight_collection_remove"
    bl_label = "Remove Weight Collection"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        if obj is None or obj.type != 'MESH':
            return False
        props = getattr(obj, "weight_collections_props", None)
        return (
            props is not None
            and len(props.collections) > 0
            and 0 <= props.active_collection_index < len(props.collections)
        )

    def execute(self, context):
        obj = context.object
        props = obj.weight_collections_props

        idx = props.active_collection_index
        if 0 <= idx < len(props.collections):
            props.collections.remove(idx)
            if len(props.collections) == 0:
                props.active_collection_index = -1
            else:
                props.active_collection_index = min(idx, len(props.collections) - 1)

        return {'FINISHED'}


class OBJECT_OT_weight_collection_add_group(Operator):
    """Aktif vertex group'u seçili weight collection'a ekler"""

    bl_idname = "object.weight_collection_add_group"
    bl_label = "Add Active Group to Collection"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        if obj is None or obj.type != 'MESH':
            return False
        if not obj.vertex_groups:
            return False
        props = getattr(obj, "weight_collections_props", None)
        if props is None or len(props.collections) == 0:
            return False
        return 0 <= props.active_collection_index < len(props.collections)

    def execute(self, context):
        obj = context.object
        props = obj.weight_collections_props

        vg_index = obj.vertex_groups.active_index
        if vg_index < 0 or vg_index >= len(obj.vertex_groups):
            self.report({'WARNING'}, "No active vertex group selected")
            return {'CANCELLED'}

        vg = obj.vertex_groups[vg_index]
        collection = props.collections[props.active_collection_index]

        for g in collection.groups:
            if g.group_name == vg.name:
                self.report({'INFO'}, f"Vertex group '{vg.name}' is already in this collection")
                return {'CANCELLED'}

        item = collection.groups.add()
        item.group_name = vg.name

        return {'FINISHED'}


class WEIGHTR2_OT_set_vertex_weight(Operator):
    """Seçili vertex'in bu gruptaki ağırlığını değiştirir."""

    bl_idname = "weightr2.set_vertex_weight"
    bl_label = "Set Vertex Weight"
    bl_options = {"REGISTER", "UNDO"}

    vertex_index: IntProperty(name="Vertex Index", default=-1)
    group_name: StringProperty(name="Group", default="")
    weight: FloatProperty(
        name="Weight",
        default=0.0,
        min=0.0,
        max=1.0,
        soft_min=0.0,
        soft_max=1.0,
        step=10,
        precision=3,
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=280)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "weight", slider=True)

    def execute(self, context):
        obj = context.object
        if not obj or obj.type != "MESH" or self.group_name not in obj.vertex_groups:
            return {"CANCELLED"}
        if self.vertex_index < 0 or self.vertex_index >= len(obj.data.vertices):
            return {"CANCELLED"}
        w = max(0.0, min(1.0, self.weight))
        prev_mode = obj.mode
        try:
            if prev_mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            obj.vertex_groups[self.group_name].add([self.vertex_index], w, "REPLACE")
        finally:
            if prev_mode != "OBJECT" and obj.mode == "OBJECT":
                bpy.ops.object.mode_set(mode=prev_mode)
        return {"FINISHED"}


class WEIGHTR2_OT_set_active_vertex_group(Operator):
    """Listeden tıklanınca bu vertex group'u aktif yapar (weight paint için seçer)"""

    bl_idname = "weightr2.set_active_vertex_group"
    bl_label = "Set Active Vertex Group"
    bl_options = {"REGISTER", "UNDO"}

    group_name: StringProperty(
        name="Group Name",
        description="Aktif yapılacak vertex group adı",
        default="",
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.type == "MESH" and obj.vertex_groups

    def execute(self, context):
        obj = context.object
        if self.group_name not in obj.vertex_groups:
            self.report({"WARNING"}, f"Vertex group '{self.group_name}' bulunamadı")
            return {"CANCELLED"}
        idx = obj.vertex_groups.find(self.group_name)
        obj.vertex_groups.active_index = idx
        return {"FINISHED"}


class OBJECT_OT_weight_collection_remove_group(Operator):
    """Seçili weight collection'dan bir vertex group'u çıkarır"""

    bl_idname = "object.weight_collection_remove_group"
    bl_label = "Remove Group from Collection"
    bl_options = {'REGISTER', 'UNDO'}

    group_name: StringProperty(
        name="Group Name",
        description="Vertex group name to remove from collection",
        default="",
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        if obj is None or obj.type != 'MESH':
            return False
        props = getattr(obj, "weight_collections_props", None)
        if props is None or len(props.collections) == 0:
            return False
        return 0 <= props.active_collection_index < len(props.collections)

    def execute(self, context):
        obj = context.object
        props = obj.weight_collections_props
        collection = props.collections[props.active_collection_index]

        remove_index = -1
        for idx, g in enumerate(collection.groups):
            if g.group_name == self.group_name:
                remove_index = idx
                break

        if remove_index == -1:
            self.report({'WARNING'}, f"Group '{self.group_name}' not found in collection")
            return {'CANCELLED'}

        collection.groups.remove(remove_index)
        if collection.active_group_index >= len(collection.groups):
            collection.active_group_index = len(collection.groups) - 1

        return {'FINISHED'}


def _get_vertex_weight_pairs(obj, mesh, v_index):
    """Vertex'in vertex group ağırlıklarını (group_index, weight) listesi olarak döndürür. Sadece okuma."""
    if v_index < 0 or v_index >= len(mesh.vertices):
        return []
    vertex = mesh.vertices[v_index]
    pairs = [(g.group, g.weight) for g in vertex.groups if 0 <= g.group < len(obj.vertex_groups)]
    if not pairs:
        try:
            dg = bpy.context.evaluated_depsgraph_get()
            obj_eval = obj.evaluated_get(dg)
            meval = obj_eval.data
            if v_index < len(meval.vertices):
                vertex = meval.vertices[v_index]
                pairs = [(g.group, g.weight) for g in vertex.groups if 0 <= g.group < len(obj.vertex_groups)]
        except Exception:
            pass
    return pairs


def _get_selected_vertex_indices(context):
    """Mevcut moda göre seçili vertex indekslerini döndürür (Edit'te bmesh, diğer modlarda mesh.select)."""
    obj = context.object
    if obj is None or obj.type != "MESH":
        return []
    mesh = obj.data
    if context.mode == "EDIT_MESH":
        try:
            bm = bmesh.from_edit_mesh(mesh)
            if bm is None:
                return [v.index for v in mesh.vertices if v.select]
            return [v.index for v in bm.verts if v.select]
        except Exception:
            return [v.index for v in mesh.vertices if v.select]
    return [v.index for v in mesh.vertices if v.select]


def _draw_weightr2_panel(layout, context):
    """Ortak panel içeriği — Object, Edit ve Weight Paint modlarında aynı UI."""
    obj = context.object
    if obj is None or obj.type != "MESH":
        layout.label(text="Select a mesh object", icon="ERROR")
        return

    # Vertex Groups List
    box = layout.box()
    box.label(text="Vertex Groups", icon="GROUP_VERTEX")
    if obj.vertex_groups:
        row = box.row()
        row.template_list(
            "WEIGHTR2_UL_vertex_groups",
            "",
            obj,
            "vertex_groups",
            obj.vertex_groups,
            "active_index",
            rows=5,
        )
    else:
        box.label(text="No vertex groups on object", icon="INFO")

    # Weight Collections
    props = obj.weight_collections_props
    col_box = layout.box()
    header = col_box.row()
    header.label(text="Weight Collections", icon="OUTLINER_COLLECTION")
    header.operator("object.weight_collection_add", text="", icon="ADD")
    header.operator("object.weight_collection_remove", text="", icon="REMOVE")
    row = col_box.row()
    row.template_list(
        "UI_UL_list",
        "WEIGHTR2_Collections",
        props,
        "collections",
        props,
        "active_collection_index",
        rows=3,
    )
    active_collection = None
    if 0 <= props.active_collection_index < len(props.collections):
        active_collection = props.collections[props.active_collection_index]
    if active_collection:
        groups_box = col_box.box()
        groups_box.label(text="Groups in Collection", icon="GROUP_VERTEX")
        if active_collection.groups:
            for g in active_collection.groups:
                row = groups_box.row(align=True)
                idx = obj.vertex_groups.find(g.group_name) if g.group_name in obj.vertex_groups else -1
                is_active = idx >= 0 and obj.vertex_groups.active_index == idx
                op = row.operator(
                    "weightr2.set_active_vertex_group",
                    text=g.group_name,
                    icon="RADIOBUT_ON" if is_active else "RADIOBUT_OFF",
                )
                op.group_name = g.group_name
                op = row.operator("object.weight_collection_remove_group", text="", icon="X")
                op.group_name = g.group_name
        else:
            groups_box.label(text="No groups in this collection", icon="INFO")
        controls = col_box.row(align=True)
        controls.operator("object.weight_collection_add_group", text="Add Active Group", icon="ADD")

    # Selected Vertex Weights — Blender Item paneli gibi: her draw'da seçimi oku, cache yok, anında güncellenir
    weights_box = layout.box()
    weights_box.label(text="Selected Vertex Weights", icon="VERTEXSEL")
    mesh = obj.data
    selected_vertex_indices = _get_selected_vertex_indices(context)
    if not selected_vertex_indices:
        weights_box.label(text="No selected vertices.", icon="INFO")
        if context.mode == "EDIT_MESH":
            weights_box.label(text="Select vertices in Edit mode.")
        elif context.mode == "WEIGHT_PAINT":
            weights_box.label(text="Use Vertex Selection mask or select in Edit mode first.")
        else:
            weights_box.label(text="Switch to Edit or Weight Paint and select vertices.")
        return
    v_index = selected_vertex_indices[0]
    weight_pairs = _get_vertex_weight_pairs(obj, mesh, v_index)
    if not weight_pairs:
        weights_box.label(text=f"Vertex {v_index} has no weights", icon="INFO")
        return

    for group_index, weight in weight_pairs:
        if group_index < 0 or group_index >= len(obj.vertex_groups):
            continue
        vg_name = obj.vertex_groups[group_index].name
        is_active = obj.vertex_groups.active_index == group_index
        row = weights_box.row(align=True)
        op = row.operator(
            "weightr2.set_active_vertex_group",
            text=vg_name,
            icon="RADIOBUT_ON" if is_active else "RADIOBUT_OFF",
        )
        op.group_name = vg_name
        op_weight = row.operator("weightr2.set_vertex_weight", text=f"{weight:.3f}")
        op_weight.vertex_index = v_index
        op_weight.group_name = vg_name
        op_weight.weight = weight


class WEIGHTR2_PT_WeightCollections_Object(Panel):
    """WeightR2 paneli — Object modunda."""

    bl_label = "Weight Collections"
    bl_idname = "WEIGHTR2_PT_WeightCollections_Object"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "WeightR2"
    bl_context = "objectmode"

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.type == "MESH"

    def draw(self, context):
        _draw_weightr2_panel(self.layout, context)


class WEIGHTR2_PT_WeightCollections_Edit(Panel):
    """WeightR2 paneli — Edit modunda."""

    bl_label = "Weight Collections"
    bl_idname = "WEIGHTR2_PT_WeightCollections_Edit"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "WeightR2"
    bl_context = "mesh_edit"

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.type == "MESH"

    def draw(self, context):
        _draw_weightr2_panel(self.layout, context)


class WEIGHTR2_PT_WeightCollections_WeightPaint(Panel):
    """WeightR2 paneli — Weight Paint modunda."""

    bl_label = "Weight Collections"
    bl_idname = "WEIGHTR2_PT_WeightCollections_WeightPaint"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "WeightR2"
    bl_context = "weightpaint"

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.type == "MESH"

    def draw(self, context):
        _draw_weightr2_panel(self.layout, context)


classes = (
    WEIGHTR2_UL_vertex_groups,
    WeightCollectionGroupItem,
    WeightCollectionItem,
    WeightCollectionsProperties,
    OBJECT_OT_weight_collection_add,
    OBJECT_OT_weight_collection_remove,
    OBJECT_OT_weight_collection_add_group,
    OBJECT_OT_weight_collection_remove_group,
    WEIGHTR2_OT_set_vertex_weight,
    WEIGHTR2_OT_set_active_vertex_group,
    WEIGHTR2_PT_WeightCollections_Object,
    WEIGHTR2_PT_WeightCollections_Edit,
    WEIGHTR2_PT_WeightCollections_WeightPaint,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Object.weight_collections_props = PointerProperty(
        type=WeightCollectionsProperties
    )


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    if hasattr(bpy.types.Object, "weight_collections_props"):
        del bpy.types.Object.weight_collections_props


if __name__ == "__main__":
    register()

