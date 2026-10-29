"""Menús por rol: security.fn_my_menus() según los roles del usuario de la transacción."""

from conftest import denied


def role_id(db, admin):
    return db.execute(
        "SELECT id FROM security.role WHERE is_admin = %s ORDER BY id LIMIT 1", (admin,)
    ).fetchone()[0]


def make_user(db, username, roles):
    db.execute("RESET ROLE")
    (uid,) = db.execute(
        "INSERT INTO security.user (username, email, password_hash) "
        "VALUES (%s, %s || '@t.local', 'x') RETURNING id",
        (username, username),
    ).fetchone()
    for rid in roles:
        db.execute("INSERT INTO security.user_role (user_id, role_id) VALUES (%s, %s)", (uid, rid))
    return uid


def menus_of(db, uid):
    db.execute("SET ROLE ceragen_app")
    db.execute("SELECT set_config('app.user_id', %s, true)", ("" if uid is None else str(uid),))
    (menus,) = db.execute("SELECT security.fn_my_menus()").fetchone()
    db.execute("RESET ROLE")
    return {g["module"]: [m["path"] for m in g["menus"]] for g in menus}


def setup_menus(db, staff_role):
    """Módulo de prueba con un menú para el rol staff_role y otro solo para admins."""
    (mod,) = db.execute(
        "INSERT INTO security.module (name, sort_order) VALUES ('Prueba', 99) RETURNING id"
    ).fetchone()
    (staff_menu,) = db.execute(
        "INSERT INTO security.menu (module_id, name, path, icon) "
        "VALUES (%s, 'Agenda', '/t-agenda', 'calendar') RETURNING id",
        (mod,),
    ).fetchone()
    db.execute(
        "INSERT INTO security.menu (module_id, name, path, icon) "
        "VALUES (%s, 'Ajustes', '/t-ajustes', 'settings')",
        (mod,),
    )
    db.execute("INSERT INTO security.menu_role (menu_id, role_id) VALUES (%s, %s)", (staff_menu, staff_role))
    return mod, staff_menu


def test_admin_sees_everything_and_staff_only_assigned(db):
    staff = role_id(db, admin=False)
    setup_menus(db, staff)
    admin = make_user(db, "t_admin", [role_id(db, admin=True)])
    worker = make_user(db, "t_worker", [staff])

    assert menus_of(db, admin)["Prueba"] == ["/t-agenda", "/t-ajustes"]
    assert menus_of(db, worker)["Prueba"] == ["/t-agenda"]
    assert menus_of(db, worker)["General"] == ["/"]  # la semilla da Inicio a los roles no admin


def test_inactive_menu_module_or_assignment_disappears(db):
    staff = role_id(db, admin=False)
    mod, staff_menu = setup_menus(db, staff)
    worker = make_user(db, "t_worker", [staff])

    db.execute("UPDATE security.menu_role SET is_active = false WHERE menu_id = %s", (staff_menu,))
    assert "Prueba" not in menus_of(db, worker)
    db.execute("UPDATE security.menu_role SET is_active = true WHERE menu_id = %s", (staff_menu,))

    db.execute("UPDATE security.module SET is_active = false WHERE id = %s", (mod,))
    assert "Prueba" not in menus_of(db, worker)


def test_no_user_or_no_roles_means_no_menus(db):
    lonely = make_user(db, "t_lonely", [])
    assert menus_of(db, None) == {}
    assert menus_of(db, lonely) == {}


def test_app_cannot_read_menu_tables_directly(db):
    db.execute("SET ROLE ceragen_app")
    for table in ("security.module", "security.menu", "security.menu_role"):
        assert denied(db, f"SELECT * FROM {table}"), table  # noqa: S608
