bl_info = {
    "name": "Pryzm 3D Geo & AI Builder",
    "author": "Pryzm Studios",
    "version": (1, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Pryzm Tools",
    "description": "Real OSM geo-data building generator and AI 3D bridge for Blender.",
    "category": "Add Mesh",
}

import bpy
import bmesh
import requests

# --- دالة تحويل إحداثيات GPS إلى إحداثيات محلية في بلندر ---
def gps_to_local(lat, lon, ref_lat, ref_lon):
    # تحويل تقريبي بسيط للمتر (كل درجة تقريبا 111111 متر)
    scale = 111111.0
    x = (lon - ref_lon) * scale * 0.74 # تقريب نسبة خطوط الطول حسب خط العرض
    y = (lat - ref_lat) * scale
    return (x, y)

# --- 1. Operator: جلب المباني الحقيقية من الخرائط عبر Overpass API ---
class PRYZM_OT_generate_from_street(bpy.types.Operator):
    bl_idname = "pryzm.generate_from_street"
    bl_label = "Build Real City/Street 3D"
    bl_description = "Fetch real building vectors from OpenStreetMap and generate 3D geometry"

    def execute(self, context):
        place_name = context.scene.pryzm_street_input
        if not place_name:
            self.report({'ERROR'}, "Please enter a location or area name!")
            return {'CANCELLED'}
        
        self.report({'INFO'}, f"Connecting to OpenStreetMap for: {place_name}...")
        
        # استعلام Overpass API لجلب المباني مع إحداثياتها وارتفاعاتها
        overpass_url = "https://overpass-api.de/api/interpreter"
        overpass_query = f"""
        [out:json][timeout:25];
        area[name="{place_name}"]->.searchArea;
        (
          way["building"](area.searchArea);
        );
        out body;
        >;
        out skel qt;
        """
        
        try:
            response = requests.post(overpass_url, data={'data': overpass_query})
            data = response.json()
        except Exception as e:
            self.report({'ERROR'}, f"Failed to connect to API: {str(e)}")
            return {'CANCELLED'}
        
        elements = data.get('elements', [])
        if not elements:
            self.report({'WARNING'}, "No buildings found for this location. Try a larger district name.")
            return {'CANCELLED'}

        # فصل النقاط (Nodes) عن الطرق (Ways)
        nodes = {el['id']: (el['lat'], el['lon']) for el in elements if el['type'] == 'node'}
        ways = [el for el in elements if el['type'] == 'way']

        if not nodes or not ways:
            self.report({'ERROR'}, "Insufficient spatial data returned.")
            return {'CANCELLED'}

حجم المرجع الأول للإحداثيات لتوسيط المشهد
        ref_node = list(nodes.values())[0]
        ref_lat, ref_lon = ref_node[0], ref_node[1]

        # إنشاء Mesh رئيسي يجمع كل مباني المنطقة
        mesh = bpy.data.meshes.new(f"CityBlock_{place_name}")
        obj = bpy.data.objects.new(f"District_{place_name}", mesh)
        context.collection.objects.link(obj)
        context.view_layer.objects.active = obj
        obj.select_set(True)

        bm = bmesh.new()

        created_count = 0
        for way in ways:
            way_nodes = way.get('nodes', [])
            if len(way_nodes) < 3:
                continue
            
            # استخراج النقاط الخاصة بالمبنى وتحويلها لإحداثيات 3D
            verts = []
            valid_way = True
            for node_id in way_nodes:
                if node_id in nodes:
                    lat, lon = nodes[node_id]
                    x, y = gps_to_local(lat, lon, ref_lat, ref_lon)
                    verts.append(bm.verts.new((x, y, 0.0)))
                else:
                    valid_way = False
                    break
            
            if valid_way and len(verts) >= 3:
                try:
                    face = bm.faces.new(verts)
                    # تحديد ارتفاع المبنى (إذا وجد في البيانات أو افتراضي 10 متر)
                    height = float(way.get('tags', {}).get('height', 10.0))
                    # عمل Extrude لرفع الجدران ثلاثياً
                    extruded = bmesh.ops.extrude_face_region(bm, geom=[face])
                    geom_to_translate = [element for element in extruded['geom'] if isinstance(element, bmesh.types.BMVert)]
                    bmesh.ops.translate(bm, vec=(0, 0, height), verts=geom_to_translate)
                    created_count += 1
                except Exception:
                    # تخطي أي مضلعات غير منتظمة لمنع الانهيار
                    continue

        bm.to_mesh(mesh)
        bm.free()
        
        self.report({'FINISHED'}, f"Successfully generated {created_count} 3D buildings for {place_name}!")
        return {'FINISHED'}

# --- 2. واجهة المستخدم (UI Panel) ---
class PRYZM_PT_main_panel(bpy.types.Panel):
    bl_label = "Pryzm 3D AI & Geo Studio"
    bl_idname = "PRYZM_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Pryzm Tools"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        box = layout.box()
        box.label(text="GIS & Street to 3D", icon="WORLD")
        box.prop(scene, "pryzm_street_input", text="Area / City")
        box.operator("pryzm.generate_from_street", icon="MESH_CUBE")

classes = (
    PRYZM_OT_generate_from_street,
    PRYZM_PT_main_panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.pryzm_street_input = bpy.props.StringProperty(
        name="Street Input", 
        description="Enter city or district name (e.g. New Cairo)", 
        default="New Cairo"
    )

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.pryzm_street_input

if __name__ == "__main__":
    register()
