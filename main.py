import json
import sqlite3

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Center, Grid
from textual.reactive import reactive
from textual.screen import Screen, ModalScreen
from textual.theme import Theme
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Pretty,
)
from textual.widgets.data_table import RowKey
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


class SubjectEditEntry(NamedTuple):
    subject_id: str
    subject_name: str
    added_time: str
    updated_time: str

    def to_ui(self) -> tuple[str, ...]:
        return (
            self.subject_id,
            self.subject_name,
            self.added_time,
            self.updated_time if self.added_time != self.updated_time else "-",
        )


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
            exec_connection.close()
            raise e

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
            exec_many_connection.close()
            raise e

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
            "CREATE TABLE meta_info("
            + "key TEXT PRIMARY KEY,"
            + "value"
            + ") "
            + "WITHOUT ROWID;"
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
            + "subject_id TEXT PRIMARY KEY, "
            + "subject_name TEXT, "
            + "added_time TEXT, "
            + "updated_time TEXT"
            + ");"
        )

    def db_validate_dim_subject(self) -> None:
        pass  # We just trust the process for now.

    def db_write_fact_session(self) -> None:
        self.db_execute(
            "CREATE TABLE fact_session("
            + "session_id TEXT PRIMARY KEY, "
            + "subject_id TEXT, "
            + "start_time TEXT, "
            + "end_time TEXT, "
            + "duration INT"
            + ");"
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
            ListItem(Label("(1) Begin a new study session."), id="main-menu-study"),
            ListItem(Label("(2) Add or edit a subject."), id="main-menu-subject"),
            ListItem(Label("(3) View study sessions’ table."), id="main-menu-sessions"),
            ListItem(Label("(4) View summary plots."), id="main-menu-plots"),
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
            case 1:
                self.app.install_screen(SubjectsScreen(), "Edit-Subjects")
                self.app.push_screen("Edit-Subjects")

    def on_key(self, event: events.Key) -> None:
        if event.name in "1234":
            self.query_one("#main-menu-choices", ListView).index = int(event.name) - 1
            self.query_one("#main-menu-choices", ListView).action_select_cursor()


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
        yield Footer(show_command_palette=False)

    def action_back_to_main_menu(self) -> None:
        self.app.sub_title = self.previous_sub_title
        self.app.pop_screen()
        self.app.uninstall_screen(self)


class SubjectsScreen(Screen):
    BINDINGS = [
        Binding(
            "a",
            "add_subject",
            "Add",
            show=True,
            tooltip="Add a new subject to the database",
        ),
        Binding(
            "e",
            "edit_subject",
            "Edit",
            show=True,
            tooltip="Edit the currently selected cell.",
        ),
        Binding(
            "d",
            "delete_subject",
            "Delete",
            show=True,
            tooltip="Delete the currently selected subject and all related study sessions.",
        ),
        Binding(
            "s",
            "sort_table",
            "Sort",
            show=True,
            tooltip="Toggle between sorting the table by subject name, creation date and last update date.",
        ),
        Binding(
            "escape",
            "back_to_main_menu",
            "Main Menu",
            show=True,
            tooltip="Go back to the main menu.",
        ),
        Binding(
            "f5",
            "refresh_table",
            "Refresh table layout",
            show=False,
            tooltip="Force the refresh of the table layout.",
        ),
    ]

    sort_priority: reactive[tuple[str, str] | None] = reactive(None)

    async def on_mount(self) -> None:
        self.previous_sub_title: str = self.app.sub_title
        self.app.sub_title = "Add / Edit subjects"
        self.query_one("#subjects-table", DataTable).cursor_type = "row"
        self.refresh_table()

    def on_data_table_row_highlighted(self, event: DataTable.RowSelected) -> None:
        self.current_hi_row: int = event.cursor_row
        self.current_hi_row_key: RowKey = event.row_key
        self.current_hi_row_name: str = event.data_table.get_cell(
            self.current_hi_row_key, "Subject"
        )

    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable(id="subjects-table")
        # yield Pretty("Test")
        yield Footer(show_command_palette=False)

    def action_refresh_table(self) -> None:
        self.refresh_table()

    def refresh_table(self) -> None:
        my_tui_table: DataTable = self.query_one("#subjects-table", DataTable)
        my_tui_table.clear(columns=True)
        for col in ("Subject", "Added", "Last edit"):
            my_tui_table.add_column(col, key=col)
        my_subject_data: list[SubjectEditEntry] = [
            SubjectEditEntry(*subject_row)
            for subject_row in self.app.st_database.db_query(
                "SELECT subject_id, subject_name, added_time, updated_time FROM dim_subject;"
            )
        ]
        if my_subject_data:
            for row in my_subject_data:
                ui_row: tuple[str, ...] = row.to_ui()
                my_tui_table.add_row(*ui_row[1:], key=ui_row[0])
        # self.query_one(Pretty).update(my_tui_table.rows)

    def action_add_subject(self) -> None:
        self.app.push_screen(AddSubjectScreen())

    async def action_edit_subject(self) -> None:
        def db_edit_row(result: str | None) -> None:
            if result is not None:
                current_edit_time: str = datetime.now(tz=timezone.utc).isoformat()
                self.app.st_database.db_execute(
                    "UPDATE dim_subject SET subject_name = ?, updated_time = ? WHERE subject_id = ?;",
                    (
                        result,
                        current_edit_time,
                        self.current_hi_row_key.value,
                    ),
                    commit=True,
                )
                self.query_one("#subjects-table", DataTable).update_cell(
                    self.current_hi_row_key, "Subject", result
                )
                self.query_one("#subjects-table", DataTable).update_cell(
                    self.current_hi_row_key, "Last edit", current_edit_time
                )

        self.app.push_screen(EditSubjectScreen(), db_edit_row)

    def action_sort_table(self) -> None:
        match self.sort_priority:
            case None:
                self.sort_priority = ("Subject", "Added")
            case ("Subject", "Added"):
                self.sort_priority = ("Added", "Subject")
            case ("Added", "Subject"):
                self.sort_priority = ("Last edit", "Subject")
            case ("Last edit", "Subject"):
                self.sort_priority = ("Subject", "Added")
        self.mutate_reactive(SubjectsScreen.sort_priority)

        subjects_table_to_be_sorted: DataTable = self.query_one(
            "#subjects-table", DataTable
        )
        # self.query_one(Pretty).update(subjects_table_to_be_sorted.columns)
        subjects_table_to_be_sorted.sort(*self.sort_priority)
        self.app.notify(f"Table sorted by {self.sort_priority[0]}.", timeout=1)

    def action_back_to_main_menu(self) -> None:
        self.app.sub_title = self.previous_sub_title
        self.app.pop_screen()
        self.app.uninstall_screen(self)


class ConfirmExitScreen(ModalScreen):
    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Are you sure you want to quit?", id="prompt"),
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


class AddSubjectScreen(ModalScreen):
    def compose(self) -> ComposeResult:
        yield Grid(
            Label(
                "Insert the name of the subject and press `Enter` or the `Done` button.",
                id="prompt",
            ),
            Input(
                placeholder="Subject name",
                type="text",
                max_length=256,
                valid_empty=False,
                id="new-subject-name",
            ),
            Button("Done", variant="success", id="done-button"),
            Button("Cancel", variant="error", id="cancel-button"),
            id="dialog",
        )
        # yield Pretty("", id="debugger")

    async def on_button_pressed(self, button: Button.Pressed):
        match button.button.id:
            case "done-button":
                new_subject_input: Input = self.query_one("#new-subject-name", Input)
                if new_subject_input.is_valid:
                    await new_subject_input.action_submit()
            case "cancel-button":
                self.app.pop_screen()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        new_subject_name: str = event.value.strip()
        if not new_subject_name:
            self.app.notify(
                "Empty subject name.",
                title="Error",
                severity="error",
                timeout=3,
            )
        else:
            # self.query_one("#debugger", Pretty).update(new_subject_name)
            subject_ids: set[str] = {
                x[0]
                for x in self.app.st_database.db_query(
                    "SELECT subject_id FROM dim_subject;"
                )
            }
            subject_names: set[str] = {
                x[0].lower()
                for x in self.app.st_database.db_query(
                    "SELECT subject_name FROM dim_subject;"
                )
            }

            if new_subject_name.lower() in subject_names:
                self.app.notify(
                    "Please choose a different name or edit the existing subject.",
                    title="A subject with the same name already exists!",
                    severity="error",
                    timeout=5,
                )
            else:
                new_subject_id: str = str(uuid4())
                while new_subject_id in subject_ids:
                    new_subject_id = str(uuid4())
                new_subject_datetime: datetime = datetime.now(tz=timezone.utc)
                self.app.st_database.db_execute(
                    "INSERT INTO dim_subject VALUES(?, ?, ?, ?)",
                    (
                        new_subject_id,
                        new_subject_name,
                        new_subject_datetime.isoformat(),
                        new_subject_datetime.isoformat(),
                    ),
                    commit=True,
                )
                self.app.pop_screen()
                self.app.screen.refresh_table()

    def on_key(self, event: events.Key) -> None:
        if event.name == "escape":
            self.app.pop_screen()
            event.stop()


class EditSubjectScreen(ModalScreen[str]):
    def compose(self) -> ComposeResult:
        yield Grid(
            Label(
                "Insert the new name for the subject and press `Enter` or the `Done` button.",
                id="prompt",
            ),
            Input(
                value=self.app.get_screen(
                    "Edit-Subjects", SubjectsScreen
                ).current_hi_row_name,
                placeholder="Subject name",
                type="text",
                max_length=256,
                valid_empty=False,
                id="new-subject-name",
            ),
            Button("Done", variant="success", id="done-button"),
            Button("Cancel", variant="error", id="cancel-button"),
            id="dialog",
        )
        # yield Pretty("", id="debugger")

    async def on_button_pressed(self, button: Button.Pressed):
        match button.button.id:
            case "done-button":
                new_subject_input: Input = self.query_one("#new-subject-name", Input)
                if new_subject_input.is_valid:
                    await new_subject_input.action_submit()
            case "cancel-button":
                self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        new_subject_name: str = event.value.strip()
        if not new_subject_name:
            self.app.notify(
                "Empty subject name.",
                title="Error",
                severity="error",
                timeout=3,
            )
        elif (
            new_subject_name
            == self.app.get_screen("Edit-Subjects", SubjectsScreen).current_hi_row_name
        ):
            self.app.notify(
                "The new name should not match the previous.",
                title="Error",
                severity="error",
                timeout=3,
            )
        else:
            # self.query_one("#debugger", Pretty).update(new_subject_name)
            subject_ids: set[str] = {
                x[0]
                for x in self.app.st_database.db_query(
                    "SELECT subject_id FROM dim_subject;"
                )
            }
            subject_names: set[str] = {
                x[0].lower()
                for x in self.app.st_database.db_query(
                    "SELECT subject_name FROM dim_subject;"
                )
            }

            if new_subject_name.lower() in subject_names:
                self.app.notify(
                    "Please choose a different name or edit the existing subject.",
                    title="A subject with the same name already exists!",
                    severity="error",
                    timeout=5,
                )
            else:
                self.dismiss(result=new_subject_name)

    def on_key(self, event: events.Key) -> None:
        if event.name == "escape":
            self.app.pop_screen()
            event.stop()


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

    MainMenuScreen {
        #main-menu-title {
            display: block;
            text-style: bold underline;
            color: $primary;
            width: auto;
            margin: 1;
        }

        ListView#main-menu-choices {
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

        #prompt {
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

    AddSubjectScreen, EditSubjectScreen {
        align: center middle;

        #dialog {
            grid-size: 2;
            grid-gutter: 1 2;
            grid-rows: 1fr 1fr 3;
            width: 75%;
            padding: 0 1;
            height: 12;
            border: thick $background 80%;
            background: $surface;
            content-align: center middle;
        }

        #prompt {
            column-span: 2;
            height: 1fr;
            width: 1fr;
            content-align: center middle;
            padding-top: 1;
        }

        Input {
            column-span: 2;
        }

        Button {
            width: 100%;
        }
    }

    SubjectsScreen {
        #subjects-table {
            width: auto;
        }

        # Pretty {
        #     max-width: 30;
        # }
    }
    """

    async def on_mount(self) -> None:
        self.st_config: Config = Config()
        for theme in (unipd_light_theme, unipd_dark_theme):
            self.register_theme(theme)
        # self.query_one("#debug-line", Pretty).update(self.available_themes)
        self.theme = self.st_config.theme
        # self.query_one("#main-menu-choices").focus()
        self.push_screen("Main-Menu")
        self.st_database: Database = Database(config=self.st_config)

    def action_my_quit(self) -> None:
        self.push_screen(ConfirmExitScreen())


def main() -> None:
    app = StudyTimeApp()
    app.run()


if __name__ == "__main__":
    main()
