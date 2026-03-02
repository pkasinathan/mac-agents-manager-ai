"""Tests for LaunchService model."""
import plistlib

import pytest

from mac_agents_manager.models import ALLOWED_LOG_DIRS, LABEL_RE, LaunchService


class TestLabelValidation:
    """Label validation prevents path traversal and shell metacharacters."""

    def test_valid_label(self):
        LaunchService._validate_label("user.productivity.myapp")

    def test_valid_label_with_hyphens(self):
        LaunchService._validate_label("user.my-app.service-1")

    def test_empty_label_rejected(self):
        with pytest.raises(ValueError, match="Invalid label length"):
            LaunchService._validate_label("")

    def test_too_long_label_rejected(self):
        with pytest.raises(ValueError, match="Invalid label length"):
            LaunchService._validate_label("a" * 129)

    def test_max_length_label_accepted(self):
        LaunchService._validate_label("a" * 128)

    def test_path_traversal_rejected(self):
        with pytest.raises(ValueError, match="must not contain"):
            LaunchService._validate_label("user..evil")

    def test_shell_metacharacters_rejected(self):
        for bad in ["user;rm -rf /", "user|cat", "user&bg", "user$(cmd)", "user`cmd`"]:
            with pytest.raises(ValueError, match="invalid characters"):
                LaunchService._validate_label(bad)

    def test_slash_rejected(self):
        with pytest.raises(ValueError, match="invalid characters"):
            LaunchService._validate_label("user/../../etc/passwd")

    def test_spaces_rejected(self):
        with pytest.raises(ValueError, match="invalid characters"):
            LaunchService._validate_label("user productivity myapp")


class TestServiceId:
    """service_id round-trips through from_service_id."""

    def test_round_trip(self):
        svc = LaunchService("user.prod.app", "agent")
        restored = LaunchService.from_service_id(svc.service_id)
        assert restored.label == svc.label

    def test_missing_colon_rejected(self):
        with pytest.raises(ValueError, match="Invalid service_id"):
            LaunchService.from_service_id("nocolon")

    def test_invalid_label_in_id_rejected(self):
        with pytest.raises(ValueError, match="invalid characters"):
            LaunchService.from_service_id("agent:user;rm -rf /")


class TestFilePath:
    """file_path must resolve inside AGENTS_DIR."""

    def test_normal_label(self):
        svc = LaunchService("user.prod.app")
        path = svc.file_path
        assert path.name == "user.prod.app.plist"
        assert str(path).startswith(str(LaunchService.AGENTS_DIR.resolve()))

    def test_double_dot_blocked_by_validate(self):
        with pytest.raises(ValueError):
            LaunchService._validate_label("user..prod")


class TestNameProperty:
    def test_extracts_last_segment(self):
        svc = LaunchService("user.productivity.myservice")
        assert svc.name == "myservice"

    def test_single_segment(self):
        svc = LaunchService("standalone")
        assert svc.name == "standalone"


class TestNamespace:
    def test_user_prefix(self):
        svc = LaunchService("user.finance.tracker")
        assert svc.namespace == "finance"

    def test_com_prefix(self):
        svc = LaunchService("com.myorg.tool")
        assert svc.namespace == "myorg"

    def test_unknown_prefix(self):
        svc = LaunchService("standalone")
        assert svc.namespace == "other"


class TestCreateFromForm:
    """create_from_form validates inputs and builds correct plist data."""

    def _base_form(self, **overrides):
        form = {
            "name": "myapp",
            "category": "productivity",
            "script_path": "/usr/local/bin/myapp",
            "schedule_type": "keepalive",
        }
        form.update(overrides)
        return form

    def test_keepalive_service(self):
        svc = LaunchService.create_from_form(self._base_form())
        assert svc.label == "user.productivity.myapp"
        assert svc.data["KeepAlive"] is True
        assert "StartCalendarInterval" not in svc.data

    def test_scheduled_service(self):
        form = self._base_form(
            schedule_type="scheduled",
            schedule_hour_0="9",
            schedule_minute_0="30",
        )
        svc = LaunchService.create_from_form(form)
        assert "KeepAlive" not in svc.data
        assert svc.data["StartCalendarInterval"] == [{"Hour": 9, "Minute": 30}]

    def test_multiple_schedule_times(self):
        form = self._base_form(
            schedule_type="scheduled",
            schedule_hour_0="9",
            schedule_minute_0="0",
            schedule_hour_1="17",
            schedule_minute_1="30",
        )
        svc = LaunchService.create_from_form(form)
        assert len(svc.data["StartCalendarInterval"]) == 2

    def test_invalid_name_rejected(self):
        with pytest.raises(ValueError, match="Name must contain"):
            LaunchService.create_from_form(self._base_form(name="bad name!"))

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError, match="Name must contain"):
            LaunchService.create_from_form(self._base_form(name=""))

    def test_invalid_category_rejected(self):
        with pytest.raises(ValueError, match="Category must contain"):
            LaunchService.create_from_form(self._base_form(category="bad cat!"))

    def test_long_name_rejected(self):
        with pytest.raises(ValueError, match="64 characters"):
            LaunchService.create_from_form(self._base_form(name="a" * 65))

    def test_log_paths_auto_generated(self):
        svc = LaunchService.create_from_form(self._base_form())
        assert svc.data["StandardOutPath"] == "/tmp/user.productivity.myapp.out"
        assert svc.data["StandardErrorPath"] == "/tmp/user.productivity.myapp.err"

    def test_environment_parsed(self):
        form = self._base_form(environment="FOO=bar\nBAZ=qux")
        svc = LaunchService.create_from_form(form)
        assert svc.data["EnvironmentVariables"] == {"FOO": "bar", "BAZ": "qux"}

    def test_working_directory_set(self):
        form = self._base_form(working_directory="/tmp/myproject")
        svc = LaunchService.create_from_form(form)
        assert svc.data["WorkingDirectory"] == "/tmp/myproject"

    def test_working_directory_empty_omitted(self):
        form = self._base_form(working_directory="")
        svc = LaunchService.create_from_form(form)
        assert "WorkingDirectory" not in svc.data


class TestScheduleValidation:
    """Schedule intervals must have valid hour/minute values."""

    def _sched_form(self, hour, minute):
        return {
            "name": "test",
            "category": "test",
            "script_path": "/bin/true",
            "schedule_type": "scheduled",
            "schedule_hour_0": str(hour),
            "schedule_minute_0": str(minute),
        }

    def test_valid_range(self):
        svc = LaunchService.create_from_form(self._sched_form(0, 0))
        assert svc.data["StartCalendarInterval"] == [{"Hour": 0, "Minute": 0}]

        svc = LaunchService.create_from_form(self._sched_form(23, 59))
        assert svc.data["StartCalendarInterval"] == [{"Hour": 23, "Minute": 59}]

    def test_hour_out_of_range(self):
        with pytest.raises(ValueError, match="hour must be 0-23"):
            LaunchService.create_from_form(self._sched_form(25, 0))

    def test_minute_out_of_range(self):
        with pytest.raises(ValueError, match="minute must be 0-59"):
            LaunchService.create_from_form(self._sched_form(10, 60))

    def test_negative_hour(self):
        with pytest.raises(ValueError, match="hour must be 0-23"):
            LaunchService.create_from_form(self._sched_form(-1, 0))

    def test_non_numeric_rejected(self):
        with pytest.raises(ValueError, match="must be integers"):
            LaunchService.create_from_form(self._sched_form("abc", 0))


class TestBuildProgramArguments:
    """_build_program_arguments handles scripts, interpreters, and redirections."""

    def test_shell_script_gets_bash(self):
        result = LaunchService._build_program_arguments({"script_path": "/tmp/run.sh"})
        assert result == ["/bin/bash", "/tmp/run.sh"]

    def test_python_script_gets_python3(self):
        result = LaunchService._build_program_arguments({"script_path": "/tmp/run.py"})
        assert result == ["python3", "/tmp/run.py"]

    def test_explicit_interpreter_preserved(self):
        result = LaunchService._build_program_arguments(
            {"script_path": "/usr/bin/python3 /tmp/run.py"}
        )
        assert result == ["/usr/bin/python3", "/tmp/run.py"]

    def test_redirections_stripped(self):
        result = LaunchService._build_program_arguments(
            {"script_path": "/bin/bash /tmp/run.sh > /tmp/out.log 2>&1"}
        )
        assert ">" not in result
        assert "2>&1" not in result
        assert "/bin/bash" in result
        assert "/tmp/run.sh" in result

    def test_empty_script_path(self):
        result = LaunchService._build_program_arguments({"script_path": ""})
        assert result == []


class TestParseEnvironment:
    def test_parses_key_value(self):
        result = LaunchService._parse_environment("FOO=bar\nBAZ=qux")
        assert result == {"FOO": "bar", "BAZ": "qux"}

    def test_value_with_equals(self):
        result = LaunchService._parse_environment("PATH=/usr/bin:/bin")
        assert result == {"PATH": "/usr/bin:/bin"}

    def test_empty_string(self):
        assert LaunchService._parse_environment("") == {}

    def test_whitespace_trimmed(self):
        result = LaunchService._parse_environment("  FOO = bar  ")
        assert result == {"FOO": "bar"}


class TestFromFile:
    """from_file loads plist data and validates labels."""

    def test_valid_plist(self, tmp_path):
        plist_data = {
            "Label": "user.test.myapp",
            "ProgramArguments": ["/bin/true"],
            "KeepAlive": True,
        }
        plist_file = tmp_path / "user.test.myapp.plist"
        with open(plist_file, "wb") as f:
            plistlib.dump(plist_data, f)

        svc = LaunchService.from_file(plist_file)
        assert svc is not None
        assert svc.label == "user.test.myapp"
        assert svc.data["KeepAlive"] is True

    def test_invalid_plist_returns_none(self, tmp_path):
        bad_file = tmp_path / "bad.plist"
        bad_file.write_text("not a plist")
        assert LaunchService.from_file(bad_file) is None

    def test_missing_file_returns_none(self, tmp_path):
        assert LaunchService.from_file(tmp_path / "nonexistent.plist") is None


class TestScheduleType:
    def test_keepalive(self):
        svc = LaunchService("user.test.app")
        svc.data = {"KeepAlive": True}
        assert svc.get_schedule_type() == "keepalive"

    def test_scheduled(self):
        svc = LaunchService("user.test.app")
        svc.data = {"StartCalendarInterval": [{"Hour": 10, "Minute": 0}]}
        assert svc.get_schedule_type() == "scheduled"

    def test_unknown(self):
        svc = LaunchService("user.test.app")
        svc.data = {}
        assert svc.get_schedule_type() == "unknown"


class TestGetScheduleTimes:
    def test_list(self):
        svc = LaunchService("user.test.app")
        svc.data = {"StartCalendarInterval": [{"Hour": 10, "Minute": 0}]}
        assert svc.get_schedule_times() == [{"Hour": 10, "Minute": 0}]

    def test_single_dict_wrapped(self):
        svc = LaunchService("user.test.app")
        svc.data = {"StartCalendarInterval": {"Hour": 10, "Minute": 0}}
        assert svc.get_schedule_times() == [{"Hour": 10, "Minute": 0}]

    def test_empty(self):
        svc = LaunchService("user.test.app")
        svc.data = {}
        assert svc.get_schedule_times() == []


class TestUpdateFromForm:
    def test_switch_keepalive_to_scheduled(self):
        svc = LaunchService("user.test.app")
        svc.data = {"Label": "user.test.app", "KeepAlive": True,
                     "ProgramArguments": ["/bin/true"]}
        svc.update_from_form({
            "script_path": "/bin/true",
            "schedule_type": "scheduled",
            "schedule_hour_0": "14",
            "schedule_minute_0": "30",
        })
        assert "KeepAlive" not in svc.data
        assert svc.data["StartCalendarInterval"] == [{"Hour": 14, "Minute": 30}]

    def test_switch_scheduled_to_keepalive(self):
        svc = LaunchService("user.test.app")
        svc.data = {"Label": "user.test.app",
                     "StartCalendarInterval": [{"Hour": 10, "Minute": 0}],
                     "ProgramArguments": ["/bin/true"]}
        svc.update_from_form({
            "script_path": "/bin/true",
            "schedule_type": "keepalive",
        })
        assert svc.data["KeepAlive"] is True
        assert "StartCalendarInterval" not in svc.data

    def test_removes_working_directory_when_empty(self):
        svc = LaunchService("user.test.app")
        svc.data = {"Label": "user.test.app", "WorkingDirectory": "/old",
                     "ProgramArguments": ["/bin/true"]}
        svc.update_from_form({
            "script_path": "/bin/true",
            "schedule_type": "keepalive",
            "working_directory": "",
        })
        assert "WorkingDirectory" not in svc.data


class TestToDict:
    def test_contains_required_keys(self):
        svc = LaunchService("user.test.app")
        svc.data = {"Label": "user.test.app", "KeepAlive": True,
                     "ProgramArguments": ["/bin/true"]}
        d = svc.to_dict()
        required = {"service_id", "label", "name", "namespace", "service_type",
                     "program", "schedule_type", "schedule_times",
                     "working_directory", "environment", "log_paths", "plist_xml",
                     "port"}
        assert required.issubset(d.keys())


class TestAllowedLogDirs:
    """ALLOWED_LOG_DIRS covers macOS /private symlink resolution."""

    def test_tmp_covered(self):
        assert "/tmp/" in ALLOWED_LOG_DIRS
        assert "/private/tmp/" in ALLOWED_LOG_DIRS

    def test_var_log_covered(self):
        assert "/var/log/" in ALLOWED_LOG_DIRS
        assert "/private/var/log/" in ALLOWED_LOG_DIRS

    def test_var_folders_covered(self):
        assert "/var/folders/" in ALLOWED_LOG_DIRS
        assert "/private/var/folders/" in ALLOWED_LOG_DIRS


class TestLabelRegex:
    """LABEL_RE allows only safe characters."""

    def test_allows_alphanumeric_dot_hyphen_underscore(self):
        assert LABEL_RE.match("user.prod-app_1")

    def test_rejects_spaces(self):
        assert not LABEL_RE.match("has space")

    def test_rejects_semicolons(self):
        assert not LABEL_RE.match("user;cmd")

    def test_rejects_slashes(self):
        assert not LABEL_RE.match("user/path")
