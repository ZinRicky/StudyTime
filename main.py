import json
import sqlite3

from collections.abc import Mapping, Sequence
from datetime import datetime
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Center, Grid
from textual.screen import Screen, ModalScreen
from textual.theme import Theme
from textual.widgets import Button, Footer, Header, Label, ListItem, ListView, Pretty
from typing import NamedTuple
from uuid import uuid4

unipd_light_theme: Theme = Theme(
    name="unipd-light",
    primary="#9B0014",
    accent="#213B4A",
    foreground="#484F59",
    background="#F0F0F0",
    warning="#E2B602",
    error="#4F010B",
    success="#009B14",
    surface="#D8D8D8",
    panel="#D0D0D0",
    dark=False,
    variables={
        "footer-key-foreground": "#9B0014",
    },
)

unipd_dark_theme: Theme = Theme(
    name="unipd-dark",
    primary="#9B0014",
    secondary="#484F59",
    accent="#213B4A",
    foreground="#F0F0F0",
    background="#0A0A0A",
    warning="#E2B602",
    error="#4F010B",
    success="#009B14",
    surface="#484F59",
    panel="#1e1e1e",
    dark=True,
    variables={
        "footer-key-foreground": "#9B0014",
    },
)


class SQLiteMasterTableEntry(NamedTuple):
    type: str
    name: str
    tbl_name: str
    rootpage: int
    sql: str


class Config:
    def __init__(self, filename: str = "config.json") -> None:
        """
        Loads provided configuration file.
        If nothing is there, proceed with current version’s defaults.
        """
        raw_settings: dict
        try:
            with open(filename, encoding="utf-8") as fp:
                raw_settings = json.load(fp)
        except FileNotFoundError:
            raw_settings = dict()

        # Actual initialisation of configuration object
        self.database_file: str = (
            "studytime.db"
            if "database_file" not in raw_settings
            else raw_settings["database-file"]
        )
        self.version: int = (
            1 if "version" not in raw_settings else raw_settings["version"]
        )
        self.theme: str = (
            "unipd-dark" if "theme" not in raw_settings else raw_settings["theme"]
        )


class Database:
    def __init__(self, config: Config) -> None:
        self.database_file: str = config.database_file
        self.version: int = config.version
        self.first_connection()

    def db_execute(
        self,
        command: str,
        parameters: Mapping | Sequence | None = None,
        commit: bool = False,
    ) -> None:
        """
        Single database operation without any returned values.
        """
        exec_connection: sqlite3.Connection = sqlite3.connect(self.database_file)
        try:
            exec_cursor: sqlite3.Cursor = exec_connection.cursor()
            exec_cursor.execute(command, parameters if parameters is not None else ())
            if commit:
                exec_connection.commit()
        except sqlite3.ProgrammingError as e:
            raise e
        finally:
            exec_connection.close()

    def db_execute_many(
        self,
        command: str,
        parameters: Mapping | Sequence,
        commit: bool = True,
    ) -> None:
        """
        Multiple database operations without any returned values.
        """
        exec_many_connection: sqlite3.Connection = sqlite3.connect(self.database_file)
        try:
            exec_many_cursor: sqlite3.Cursor = exec_many_connection.cursor()
            exec_many_cursor.executemany(command, parameters)
            if commit:
                exec_many_connection.commit()
        except sqlite3.ProgrammingError as e:
            raise e
        finally:
            exec_many_connection.close()

    def db_query(self, command: str) -> list[tuple]:
        """
        Result of a query to the database.
        Please note that nothing checks whether the SQL command is a SELECT.
        """
        query_connection: sqlite3.Connection = sqlite3.connect(self.database_file)
        query_cursor: sqlite3.Cursor = query_connection.cursor()
        query_cursor.execute(command)
        query_result: list[tuple] = query_cursor.fetchall()
        query_connection.close()
        return query_result

    def db_write_meta_info(self) -> None:
        self.db_execute(
            "CREATE TABLE meta_info(key TEXT PRIMARY KEY, value) WITHOUT ROWID;"
        )
        meta_info_data: list[tuple[str, str]] = [("Version", str(self.version))]
        self.db_execute_many("INSERT INTO meta_info VALUES(?, ?);", meta_info_data)

    def db_validate_meta_info(self) -> None:
        meta_info_version_check: list[tuple] = self.db_query(
            "SELECT value FROM meta_info WHERE key = 'Version';"
        )
        if not (
            len(meta_info_version_check)
            or int(meta_info_version_check[0][0]) == self.version
        ):
            raise NotImplementedError  # We just trust the process for now.

    def db_write_dim_subject(self) -> None:
        self.db_execute(
            "CREATE TABLE dim_subject("
            + "subject_id TEXT PRIMARY KEY, subject_name TEXT, added_time TEXT);"
        )

    def db_validate_dim_subject(self) -> None:
        pass  # We just trust the process for now.

    def db_write_fact_session(self) -> None:
        self.db_execute(
            "CREATE TABLE fact_session("
            + "subject_id TEXT PRIMARY KEY, start_time TEXT, end_time TEXT);"
        )

    def db_validate_fact_session(self) -> None:
        pass  # We just trust the process for now.

    def first_connection(self) -> None:
        init_tables_01: set[str] = {
            SQLiteMasterTableEntry(*x).name
            for x in self.db_query("SELECT * FROM sqlite_master;")
        }

        if "meta_info" not in init_tables_01:
            self.db_write_meta_info()
        else:
            self.db_validate_meta_info()
        if "dim_subject" not in init_tables_01:
            self.db_write_dim_subject()
        else:
            self.db_validate_dim_subject()
        if "fact_session" not in init_tables_01:
            self.db_write_fact_session()
        else:
            self.db_validate_fact_session()


class MainMenuScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header()
        with Center():
            yield Label(
                "Select one of the following options or press '[b]q[/]' to quit.",
                id="main-menu-title",
            )
        yield ListView(
            ListItem(Label("1. Begin a new study session."), id="main-menu-study"),
            ListItem(Label("2. Add a new subject."), id="main-menu-subject"),
            ListItem(Label("3. View study sessions’ table."), id="main-menu-sessions"),
            ListItem(Label("4. View summary plots."), id="main-menu-plots"),
            id="main-menu-choices",
        )
        # yield Pretty("", id="debug-line")
        yield Footer(show_command_palette=False)

    def on_list_view_highlighted(self, highlighted_item: ListView.Highlighted) -> None:
        for item in highlighted_item.list_view.query(ListItem):
            if "-highlight" in item.classes:
                item.query_one(Label).update("> " + str(item.query_one(Label).content))
            else:
                item.query_one(Label).update(
                    str(item.query_one(Label).content).replace("> ", "")
                )

    def on_list_view_selected(self, highlighted_item: ListView.Selected) -> None:
        match highlighted_item.index:
            case 0:
                self.app.install_screen(NewStudySessionScreen(), "Study-Session")
                self.app.push_screen("Study-Session")


class ConfirmExitScreen(ModalScreen):
    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Are you sure you want to quit?", id="question"),
            Button("Quit", variant="error", id="quit"),
            Button("Cancel", variant="primary", id="cancel"),
            id="dialog",
        )

    def on_mount(self) -> None:
        self.previous_sub_title: str = self.app.sub_title
        self.app.sub_title = "Exiting…"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "quit":
            self.app.exit()
        else:
            self.app.sub_title = self.previous_sub_title
            self.app.pop_screen()

    def on_key(self, event: events.Key) -> None:
        match event.name:
            case "left":
                self.app.action_focus_previous()
            case "right":
                self.app.action_focus_next()
            case _:
                pass


class NewStudySessionScreen(Screen):
    BINDINGS = [
        Binding(
            "escape",
            "back_to_main_menu",
            "Main Menu",
            show=True,
            tooltip="Decide whether you want to save the current "
            + "study session (if any) and go back to the main menu.",
        )
    ]

    def on_mount(self) -> None:
        self.previous_sub_title: str = self.app.sub_title
        self.app.sub_title = "Study Session"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("Codroipo")
        yield Footer()

    def action_back_to_main_menu(self) -> None:
        self.app.sub_title = self.previous_sub_title
        self.app.pop_screen()
        self.app.uninstall_screen(self)


class StudyTimeApp(App):
    TITLE = "StudyTime"
    SUB_TITLE = "Main Menu"

    BINDINGS = [
        Binding(
            "q",
            "my_quit",
            "Quit",
            tooltip="Quit the program with a confirmation pop-up.",
        ),
        Binding(
            "Q",
            "quit",
            "Quit without saving",
            show=False,
        ),
    ]

    SCREENS = {"Main-Menu": MainMenuScreen}

    CSS = """
    Screen {
        align: center middle;
    }

    #main-menu-title {
        display: block;
        text-style: bold underline;
        color: $primary;
        width: auto;
        margin: 1;
    }

    ListView {
        align-horizontal: center;
        height: auto;
        background: $background;

        &:focus {
            background-tint: $background;
        }

        ListItem {
            width: 35;
            margin: 1;
            padding-left: 2;
            color: $text;
            background: $background;

            &.-highlight {
                color: $primary;
                text-style: underline;
                padding-left: 0;
            }

            &:hover {
                text-style: underline;
            }
        }
    }

    ConfirmExitScreen {
        align: center middle;

        #dialog {
            grid-size: 2;
            grid-gutter: 1 2;
            grid-rows: 1fr 3;
            width: 60;
            padding: 0 1;
            height: 11;
            border: thick $background 80%;
            background: $surface;
        }

        #question {
            column-span: 2;
            height: 1fr;
            width: 1fr;
            content-align: center middle;
        }

        Button {
            width: 100%;

            &#cancel {
                background: $accent;
                border-top: tall $accent-lighten-1;
                border-bottom: tall $accent-darken-1;
            }
        }
    }
    """

    async def on_mount(self) -> None:
        self.st_config: Config = Config()
        for theme in (unipd_light_theme, unipd_dark_theme):
            self.register_theme(theme)
        # self.query_one("#debug-line", Pretty).update(self.available_themes)
        self.theme = self.st_config.theme
        # self.query_one("#main-menu-choices").focus()
        self.st_database: Database = Database(config=self.st_config)

        self.push_screen("Main-Menu")

    def action_my_quit(self) -> None:
        self.push_screen(ConfirmExitScreen())


def main() -> None:
    app = StudyTimeApp()
    app.run()


if __name__ == "__main__":
    main()
