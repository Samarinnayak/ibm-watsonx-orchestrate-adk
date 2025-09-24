from typing import List, Dict, Any

from ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller import (
    _validate_output_file,
    _get_progress_spinner,
    _get_incomplete_tool_from_name,
    _get_tools_from_names,
    get_cpe_client,
    gather_utterances,
    pre_cpe_step,
    find_tools_by_description,
    gather_examples,
    talk_to_cpe,
    prompt_tune,
    create_agent, refine_agent_with_trajectories
)

from ibm_watsonx_orchestrate.utils.exceptions import BadRequest
from ibm_watsonx_orchestrate.agent_builder.agents import Agent, AgentKind, AgentStyle, ExternalAgent, AssistantAgent
import pytest
from requests import ConnectionError
from unittest.mock import patch, mock_open, MagicMock
from rich.progress import Progress
import os


class MockCPEClient:
    def __init__(self, pre_chat_responses=[], invoke_responses=[], mock_init_response=None,
                 refine_with_chat_response=None):
        self.pre_chat_responses = pre_chat_responses
        self.pre_chat_reponses_index = 0
        self.invoke_responses = invoke_responses
        self.invoke_responses_index = 0
        self.mock_init_response = mock_init_response
        self.mock_refine_with_chat_response = refine_with_chat_response

    def submit_pre_cpe_chat(self, **message_content):
        if not len(self.pre_chat_responses):
            return {}
        response_index = self.pre_chat_reponses_index
        self.pre_chat_reponses_index += 1

        if response_index >= len(self.pre_chat_responses):
            return self.pre_chat_responses[-1]
        else:
            return self.pre_chat_responses[response_index]

    def invoke(self, prompt):
        if not len(self.invoke_responses):
            return {}
        response_index = self.invoke_responses_index
        self.invoke_responses_index += 1

        if response_index >= len(self.invoke_responses):
            return self.invoke_responses[-1]
        else:
            return self.invoke_responses[response_index]

    def init_with_context(self, context_data):
        return self.mock_init_response

    def refine_agent_with_chats(self, instruction: str, tools: Dict[str, Any], collaborators: Dict[str, Any],
                                knowledge_bases: Dict[str, Any], trajectories_with_feedback: List[List[dict]],
                                model: str | None = None) -> dict:
        return self.mock_refine_with_chat_response


class MockToolClient:
    def __init__(self, get_response=[], get_drafts_by_names_response=[]):
        self.get_response = get_response
        self.get_drafts_by_names_response = get_drafts_by_names_response

    def get(self):
        return self.get_response

    def get_drafts_by_names(self, tool_names):
        return self.get_drafts_by_names_response


class TestValidateOutputFile:
    @pytest.mark.parametrize(
        ("output_file", "dry_run_flag"),
        [
            ("output_file.yaml", False),
            ("output_file.yml", False),
            ("output_file.json", False),
            (None, True),
        ]
    )
    def test_validate_output_file(self, output_file, dry_run_flag):
        _validate_output_file(output_file=output_file, dry_run_flag=dry_run_flag)

    def test_validate_output_file_missing_output(self, caplog):
        with pytest.raises(SystemExit):
            _validate_output_file(output_file=None, dry_run_flag=False)

        captured = caplog.text
        assert "Please provide a valid yaml output file. Or use the `--dry-run` flag to output generated agent content to terminal" in captured

    def test_validate_output_file_dry_run_with_output(self, caplog):
        with pytest.raises(SystemExit):
            _validate_output_file(output_file="output_file.yaml", dry_run_flag=True)

        captured = caplog.text
        assert "Cannot set output file when performing a dry run" in captured

    @pytest.mark.parametrize(
        "output_file",
        [
            "output_file.txt",
            "output_file.csv",
            "output_file.json.test",
            "output_file"
        ]
    )
    def test_validate_output_file_invalid_file_extention(self, output_file, caplog):
        with pytest.raises(SystemExit):
            _validate_output_file(output_file=output_file, dry_run_flag=False)

        captured = caplog.text
        assert "Output file must be of type '.yaml', '.yml' or '.json'" in captured


class TestGetProgressSpinner:
    def test_get_progress_spinner(self):
        spinner = _get_progress_spinner()
        assert isinstance(spinner, Progress)


class TestGetIncompleteToolFromName:
    @pytest.mark.parametrize(
        "tool_name",
        [
            "test_tool",
            "test_tool_2"
        ]
    )
    def test_get_incomplete_tool_from_name(self, tool_name):
        tool = _get_incomplete_tool_from_name(tool_name)

        assert tool.get("name") == tool_name
        assert tool.get("description") == tool_name
        assert tool.get("input_schema") is not None
        assert tool.get("input_schema").get("properties") == {}
        assert tool.get("output_schema") is not None
        assert tool.get("output_schema").get("description") == "None"


class TestGetToolsFromNames:
    @pytest.mark.parametrize(
        "tool_names",
        [
            ["test_tool"],
            ["test_tool", "test_tool_2"],
        ]
    )
    def test_get_tools_from_names(self, tool_names, caplog):
        with patch(
                "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.get_tool_client") as mock_get_tool_client:
            mock_response = [{"name": tool_name} for tool_name in tool_names]
            mock_get_tool_client.return_value = MockToolClient(get_drafts_by_names_response=mock_response)

            tools = _get_tools_from_names(tool_names)

            captured = caplog.text

            assert len(tools) == len(tool_names)
            assert "Failed to find tool named" not in captured
            assert "Failed to fetch tools from server" not in captured

    def test_get_tools_from_names_no_names(self):
        tools = _get_tools_from_names(tool_names=[])
        assert tools == []

    def test_get_tools_from_names_missing_tools(self, caplog):
        tool_names = ["test_tool", "test_tool_2"]
        with patch(
                "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.get_tool_client") as mock_get_tool_client:
            mock_response = [{"name": "test_tool_2"}]
            mock_get_tool_client.return_value = MockToolClient(get_drafts_by_names_response=mock_response)

            tools = _get_tools_from_names(tool_names)

            captured = caplog.text

            assert len(tools) == len(tool_names)
            assert "Failed to find tool named 'test_tool'." in captured
            assert "Failed to find tool named 'test_tool_2'." not in captured
            assert "Failed to fetch tools from server" not in captured

    def test_get_tools_from_names_server_not_started(self, caplog):
        tool_names = ["test_tool", "test_tool_2"]
        with patch(
                "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.get_tool_client") as mock_get_tool_client:
            mock_reponse = MagicMock()
            mock_reponse.get_drafts_by_names.side_effect = ConnectionError()
            mock_get_tool_client.return_value = mock_reponse

            tools = _get_tools_from_names(tool_names)

            captured = caplog.text

            assert len(tools) == len(tool_names)
            assert "Failed to find tool named " not in captured
            assert "Failed to fetch tools from server" in captured


#class TestGetCPEClient:
    # def test_get_cpe_client(self):
    #     from ibm_watsonx_orchestrate.client.copilot.cpe.copilot_cpe_client import CPEClient
    #     with patch(
    #             "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.instantiate_client") as mock_instantiate_client:
    #         get_cpe_client()
    #
    #         mock_instantiate_client.assert_called_once_with(
    #             client=CPEClient,
    #             url="http://localhost:8081"
    #         )


class TestGatherUtterances:
    @pytest.mark.parametrize(
        "max",
        [
            1,
            2,
            3
        ]
    )
    def test_gather_utterances(self, max):
        with patch("builtins.input") as mock_input:
            mock_input.side_effect = ["test"] * max
            utterances = gather_utterances(max)

        assert len(utterances) == max
        for item in utterances:
            assert item == "test"


class TestPreCPEStep:
    def test_pre_cpe_step(self):
        pre_chat_responses = [
            {
                "message": "Test Message"
            },
            {
                "description": "Test Description"
            },
            {
                "tools": []
            },
            {
                "collaborators": []
            },
            {
                "knowledge_bases": []
            },
            {
                "agent_name": "Test Agent",
                "agent_style": "Test Style",
            }
        ]
        cpe_client = MockCPEClient(pre_chat_responses=pre_chat_responses)
        with patch("builtins.input") as mock_input, \
                patch(
                    "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.get_deployed_tools_agents_and_knowledge_bases") as get_deployed_tools_agents_and_knowledge_bases:
            # , \
            # patch("ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.find_tools_by_description") as mock_find_tools_by_description,
            # patch("ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.") as XXX,
            # patch("ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.") as YYY:
            mock_input.side_effect = ["test", "test", "test", "test"]
            # mock_find_tools_by_description.return_value=[]
            get_deployed_tools_agents_and_knowledge_bases.return_value = {"tools": [], "collaborators": [],
                                                                          "knowledge_bases": []}

            pre_cpe_step(cpe_client)


class TestFindToolsByDescription:
    @pytest.mark.parametrize(
        "response",
        [
            [],
            [{"name": "tool_1"}]
        ]
    )
    def test_find_tools_by_description(self, response):
        mock_tool_client = MockToolClient(get_response=response)

        tools = find_tools_by_description("", mock_tool_client)
        assert tools == response

    def test_find_tools_by_description_server_error(self, caplog):
        mock_tool_client = MagicMock()
        mock_tool_client.get.side_effect = ConnectionError()

        tools = find_tools_by_description("", mock_tool_client)

        captured = caplog.text

        assert tools == []
        assert "Failed to contact wxo server to fetch tools" in captured


class TestGatherExamples:
    def test_gather_examples_txt(self):
        sample_data = "test1\ntest2\ntest3"
        with patch('builtins.open', mock_open(read_data=sample_data)):
            examples = gather_examples("sample_file.txt")
            assert len(examples) == 3
            assert examples == sample_data.split('\n')

    def test_gather_examples_csv(self):
        sample_data = "utterance\ntest1\ntest2\ntest3"
        with patch('builtins.open', mock_open(read_data=sample_data)):
            examples = gather_examples("sample_file.csv")
            assert len(examples) == 3
            assert examples == sample_data.split('\n')[1:]

    @pytest.mark.parametrize(
        "content",
        [
            "utterance123\ntest1\ntest2\ntest3",
            "test1\ntest2\ntest3",
            "\ntest1\ntest2\ntest3"
        ]
    )
    def test_gather_examples_csv_missing_header(self, content, caplog):
        with patch('builtins.open', mock_open(read_data=content)):
            with pytest.raises(BadRequest):
                examples = gather_examples("sample_file.csv")

        captured = caplog.text

        assert "CSV must have a column named 'utterance'" in captured

    @pytest.mark.parametrize(
        "file_name",
        [
            "file.yaml",
            "file.json",
            "file"
        ]
    )
    def test_gather_examples_unsupported_file(self, file_name, caplog):
        with pytest.raises(BadRequest):
            examples = gather_examples(file_name)

        captured = caplog.text

        assert f'Unsupported samples file format: {os.path.basename(file_name)}' in captured

    def test_gather_examples_no_file(self):
        with patch(
                "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.gather_utterances") as mock_gather_utterances:
            mock_gather_utterances.return_value = []
            examples = gather_examples()

            mock_gather_utterances.assert_called_once_with(3)


class TestTalkToCPE:
    def test_talk_to_cpe(self):
        invoke_responses = [
            {
                "response": [
                    {
                        "final_zsh_prompt": "Testing"
                    }
                ]
            }
        ]
        mock_init_response = {"response": [{}]}
        cpe_client = MockCPEClient(invoke_responses=invoke_responses, mock_init_response=mock_init_response)
        with patch("builtins.input") as mock_input, \
                patch(
                    "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.gather_examples") as mock_gather_examples:
            mock_input.side_effect = ["test"]

            response = talk_to_cpe(cpe_client, None)

            assert response == "Testing"


class TestPromptTune:
    def test_prompt_tune(self, caplog):
        with patch(
                "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.AgentsController.import_agent") as mock_import_agent, \
                patch(
                    "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.AgentsController.persist_record") as mock_persist_record, \
                patch(
                    "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.get_tool_client") as mock_get_tool_client, \
                patch(
                    "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.get_cpe_client") as mock_get_cpe_client, \
                patch(
                    "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.os.path.dirname") as mock_dirname, \
                patch(
                    "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.talk_to_cpe") as mock_talk_to_cpe:
            mock_import_agent.return_value = [Agent(
                kind=AgentKind.NATIVE,
                name="test_agent",
                description="test_agent_description"
            )]

            mock_get_cpe_client.return_value = MockCPEClient()
            mock_get_tool_client.return_value = MockToolClient()
            mock_talk_to_cpe.return_value = "Test Prompt"
            mock_dirname.return_value = False

            prompt_tune(
                agent_spec="test_agent_spec.yaml",
                output_file=None,
                samples_file=None,
                dry_run_flag=False
            )

            mock_persist_record.assert_called_once()

        captured = caplog.text
        assert "The new instruction is:" in captured

    def test_prompt_tune_dry_run(self, caplog):
        with patch(
                "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.AgentsController.import_agent") as mock_import_agent, \
                patch(
                    "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.AgentsController.persist_record") as mock_persist_record, \
                patch(
                    "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.get_tool_client") as mock_get_tool_client, \
                patch(
                    "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.get_cpe_client") as mock_get_cpe_client, \
                patch(
                    "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.os.path.dirname") as mock_dirname, \
                patch(
                    "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.talk_to_cpe") as mock_talk_to_cpe:
            mock_import_agent.return_value = [Agent(
                kind=AgentKind.NATIVE,
                name="test_agent",
                description="test_agent_description"
            )]

            mock_get_cpe_client.return_value = MockCPEClient()
            mock_get_tool_client.return_value = MockToolClient()
            mock_talk_to_cpe.return_value = "Test Prompt"
            mock_dirname.return_value = False

            prompt_tune(
                agent_spec="test_agent_spec.yaml",
                output_file=None,
                samples_file=None,
                dry_run_flag=True
            )

            mock_persist_record.assert_not_called()

        captured = caplog.text
        assert "The new instruction is:" in captured

    @pytest.mark.parametrize(
        ("agent_class", "agent_kind", "agent_params"),
        [
            (ExternalAgent, AgentKind.EXTERNAL, {"title": "test", "api_url": "test", "hidden": False, "enable_cot": False}),
            (AssistantAgent, AgentKind.ASSISTANT, {"title": "test"})
        ]
    )
    def test_prompt_tune_non_native(self, caplog, agent_class, agent_kind, agent_params):
        with patch(
                "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.AgentsController.import_agent") as mock_import_agent, \
                patch(
                    "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.AgentsController.persist_record") as mock_persist_record, \
                patch(
                    "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.get_tool_client") as mock_get_tool_client, \
                patch(
                    "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.get_cpe_client") as mock_get_cpe_client, \
                patch(
                    "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.os.path.dirname") as mock_dirname, \
                patch(
                    "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.talk_to_cpe") as mock_talk_to_cpe:
            mock_import_agent.return_value = [agent_class(
                kind=agent_kind,
                name="test_agent",
                description="test_agent_description",
                **agent_params
            )]

            mock_get_cpe_client.return_value = MockCPEClient()
            mock_get_tool_client.return_value = MockToolClient()
            mock_talk_to_cpe.return_value = "Test Prompt"
            mock_dirname.return_value = False

            with pytest.raises(SystemExit):
                prompt_tune(
                    agent_spec="test_agent_spec.yaml",
                    output_file=None,
                    samples_file=None,
                    dry_run_flag=True
                )

        captured = caplog.text
        assert f"Only native agents are supported for prompt tuning. Provided agent spec is on kind '{agent_kind}'" in captured


class TestCreateAgent:
    def test_create_agent(self):
        with patch(
                "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.AgentsController.persist_record") as mock_persist_record, \
                patch(
                    "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.get_cpe_client") as mock_get_cpe_client, \
                patch(
                    "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.get_tool_client") as mock_get_tool_client, \
                patch(
                    "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.pre_cpe_step") as mock_pre_cpe_step, \
                patch(
                    "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.os.path.dirname") as mock_dirname, \
                patch(
                    "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.talk_to_cpe") as mock_talk_to_cpe:
            mock_get_cpe_client.return_value = MockCPEClient()
            mock_get_tool_client.return_value = MockToolClient()

            mock_pre_cpe_step.return_value = {
                "tools": [],
                "description": "test description",
                "agent_name": "test_name",
                "agent_style": AgentStyle.DEFAULT,
                "collaborators": [],
                "knowledge_bases": []
            }

            mock_talk_to_cpe.return_value = "test instructions"
            mock_dirname.return_value = False

            create_agent(
                output_file="test.yaml",
                llm=None,
                samples_file=None,
            )

            mock_persist_record.assert_called()

    def test_create_agent_dry_run(self):
        with patch(
                "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.AgentsController.persist_record") as mock_persist_record, \
                patch(
                    "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.get_cpe_client") as mock_get_cpe_client, \
                patch(
                    "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.get_tool_client") as mock_get_tool_client, \
                patch(
                    "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.pre_cpe_step") as mock_pre_cpe_step, \
                patch(
                    "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.os.path.dirname") as mock_dirname, \
                patch(
                    "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.talk_to_cpe") as mock_talk_to_cpe:
            mock_get_cpe_client.return_value = MockCPEClient()
            mock_get_tool_client.return_value = MockToolClient()

            mock_pre_cpe_step.return_value = {
                "tools": [],
                "description": "test description",
                "agent_name": "test_name",
                "agent_style": AgentStyle.DEFAULT,
                "collaborators": [],
                "knowledge_bases": []
            }

            mock_talk_to_cpe.return_value = "test instructions"
            mock_dirname.return_value = False

            create_agent(
                output_file=None,
                llm=None,
                samples_file=None,
                dry_run_flag=True
            )

            mock_persist_record.assert_called_once()


class TestRefineAgentWithChat:
    mock_get_threads_messages_response = [[{"id": "ddd99e6b-f5fc-4324-9dcc-3f939378bd6a", "tenant_id": "93dc9901-12a9-46ed-8d60-f2afc5e794b0", "created_by": "f242eadf-0dc9-4eae-b2d7-65b09b4b4b16", "created_by_username": "wxo.archer@ibm.com", "created_on": "2025-08-21T08:22:07.025454Z", "updated_at": "2025-08-21T08:22:07.025454Z", "thread_id": "39d2f263-43d8-4356-ae70-69e54aeb547b", "assistant": {"is_default": True}, "parent_message_id": None, "role": "user", "content": [{"response_type": "text", "text": "I need to report for all working days next week"}], "mentions": None, "document_ids": None, "additional_properties": None, "context": None, "step_history": None, "message_state": None}, {"id": "f2fe7b13-24b2-4c4e-8a8d-a8ff157a89c3", "tenant_id": "93dc9901-12a9-46ed-8d60-f2afc5e794b0", "created_by": "f242eadf-0dc9-4eae-b2d7-65b09b4b4b16", "created_by_username": "wxo.archer@ibm.com", "created_on": "2025-08-21T08:22:14.766927Z", "updated_at": "2025-08-21T08:22:14.766927Z", "thread_id": "39d2f263-43d8-4356-ae70-69e54aeb547b", "assistant": {"is_default": True}, "parent_message_id": "ddd99e6b-f5fc-4324-9dcc-3f939378bd6a", "role": "assistant", "content": [{"response_type": "text", "id": "1", "text": "The current date is August 21, 2025. The working days next week are August 26, 27, 28, 29."}], "mentions": None, "document_ids": None, "additional_properties": {"display_properties": {"skip_render": False, "is_async": False}}, "context": None, "step_history": [{"role": "assistant", "step_details": [{"type": "tool_calls", "tool_calls": [{"id": "chatcmpl-tool-69c719ce603240679fa12932b8", "args": {}, "name": "get_current_month_working_days"}], "agent_display_name": "working_hours_recorder"}]}, {"role": "assistant", "step_details": [{"name": "get_current_month_working_days", "type": "tool_response", "content": "None", "tool_call_id": "chatcmpl-tool-69c719ce603240679fa12932b8"}, {"args": {}, "name": "get_current_month_working_days", "type": "tool_call", "tool_call_id": "chatcmpl-tool-69c719ce603240679fa12932b8"}]}, {"role": "assistant", "step_details": [{"type": "tool_calls", "tool_calls": [{"id": "chatcmpl-tool-fdb87fef2ff84034ad1bab89f8", "args": {}, "name": "get_current_date"}], "agent_display_name": "working_hours_recorder"}]}, {"role": "assistant", "step_details": [{"name": "get_current_date", "type": "tool_response", "content": "None", "tool_call_id": "chatcmpl-tool-fdb87fef2ff84034ad1bab89f8"}, {"args": {}, "name": "get_current_date", "type": "tool_call", "tool_call_id": "chatcmpl-tool-fdb87fef2ff84034ad1bab89f8"}]}], "message_state": None}, {"id": "eb58527b-f2c6-47fa-b426-e78a29a447cf", "tenant_id": "93dc9901-12a9-46ed-8d60-f2afc5e794b0", "created_by": "f242eadf-0dc9-4eae-b2d7-65b09b4b4b16", "created_by_username": "wxo.archer@ibm.com", "created_on": "2025-08-21T08:22:29.367352Z", "updated_at": "2025-08-21T08:22:29.367352Z", "thread_id": "39d2f263-43d8-4356-ae70-69e54aeb547b", "assistant": {"is_default": True}, "parent_message_id": None, "role": "user", "content": [{"response_type": "text", "text": "ok, report"}], "mentions": None, "document_ids": None, "additional_properties": None, "context": None, "step_history": None, "message_state": None}, {"id": "3d42f0f0-583e-4ff5-9a75-ef1cb9fa3a02", "tenant_id": "93dc9901-12a9-46ed-8d60-f2afc5e794b0", "created_by": "f242eadf-0dc9-4eae-b2d7-65b09b4b4b16", "created_by_username": "wxo.archer@ibm.com", "created_on": "2025-08-21T08:22:33.331332Z", "updated_at": "2025-08-21T08:22:33.331332Z", "thread_id": "39d2f263-43d8-4356-ae70-69e54aeb547b", "assistant": {"is_default": True}, "parent_message_id": "eb58527b-f2c6-47fa-b426-e78a29a447cf", "role": "assistant", "content": [{"response_type": "text", "id": "1", "text": "I need to know the start and end times for the report. What are the start and end times for the report?"}], "mentions": None, "document_ids": None, "additional_properties": {"display_properties": {"skip_render": False, "is_async": False}}, "context": None, "step_history": [{"role": "assistant", "step_details": [{"type": "tool_calls", "tool_calls": [{"id": "chatcmpl-tool-28fcf722886b4ea5828a87ac60", "args": {"type": "work", "end_time": "17:00", "start_time": "9:00", "report_date": "August 26, 27, 28, 29"}, "name": "report_time_for_day"}], "agent_display_name": "working_hours_recorder"}]}, {"role": "assistant", "step_details": [{"name": "report_time_for_day", "type": "tool_response", "content": "None", "tool_call_id": "chatcmpl-tool-28fcf722886b4ea5828a87ac60"}, {"args": {"type": "work", "end_time": "17:00", "start_time": "9:00", "report_date": "August 26, 27, 28, 29"}, "name": "report_time_for_day", "type": "tool_call", "tool_call_id": "chatcmpl-tool-28fcf722886b4ea5828a87ac60"}]}], "message_state": None}, {"id": "1fa1b2ca-abb7-41e0-be11-8ad189fbba33", "tenant_id": "93dc9901-12a9-46ed-8d60-f2afc5e794b0", "created_by": "f242eadf-0dc9-4eae-b2d7-65b09b4b4b16", "created_by_username": "wxo.archer@ibm.com", "created_on": "2025-08-21T08:22:45.464734Z", "updated_at": "2025-08-21T08:22:45.464734Z", "thread_id": "39d2f263-43d8-4356-ae70-69e54aeb547b", "assistant": {"is_default": True}, "parent_message_id": None, "role": "user", "content": [{"response_type": "text", "text": "9:00 - 17:00"}], "mentions": None, "document_ids": None, "additional_properties": None, "context": None, "step_history": None, "message_state": None}, {"id": "4596319d-52da-45a1-9ebd-83f7d994a4c3", "tenant_id": "93dc9901-12a9-46ed-8d60-f2afc5e794b0", "created_by": "f242eadf-0dc9-4eae-b2d7-65b09b4b4b16", "created_by_username": "wxo.archer@ibm.com", "created_on": "2025-08-21T08:22:56.377021Z", "updated_at": "2025-08-21T08:23:25.558688Z", "thread_id": "39d2f263-43d8-4356-ae70-69e54aeb547b", "assistant": {"is_default": True}, "parent_message_id": "1fa1b2ca-abb7-41e0-be11-8ad189fbba33", "role": "assistant", "content": [{"response_type": "text", "id": "1", "text": "The report for August 26, 27, 28, 29 has been submitted with a start time of 9:00 and an end time of 17:00."}], "mentions": None, "document_ids": None, "additional_properties": {"display_properties": {"skip_render": False, "is_async": False}}, "context": None, "step_history": [{"role": "assistant", "step_details": [{"type": "tool_calls", "tool_calls": [{"id": "chatcmpl-tool-388a34daa6064e15955a48e7ae", "args": {"type": "work", "end_time": "17:00", "start_time": "9:00", "report_date": "August 26"}, "name": "report_time_for_day"}, {"id": "chatcmpl-tool-7e1e05c11ea54086b85aafdb07", "args": {"type": "work", "end_time": "17:00", "start_time": "9:00", "report_date": "August 27"}, "name": "report_time_for_day"}, {"id": "chatcmpl-tool-e7008234c848458f8a31f84895", "args": {"type": "work", "end_time": "17:00", "start_time": "9:00", "report_date": "August 28"}, "name": "report_time_for_day"}, {"id": "chatcmpl-tool-a693cdf49b204dc7b139a67c60", "args": {"type": "work", "end_time": "17:00", "start_time": "9:00", "report_date": "August 29"}, "name": "report_time_for_day"}], "agent_display_name": "working_hours_recorder"}]}, {"role": "assistant", "step_details": [{"name": "report_time_for_day", "type": "tool_response", "content": "None", "tool_call_id": "chatcmpl-tool-388a34daa6064e15955a48e7ae"}, {"args": {"type": "work", "end_time": "17:00", "start_time": "9:00", "report_date": "August 26"}, "name": "report_time_for_day", "type": "tool_call", "tool_call_id": "chatcmpl-tool-388a34daa6064e15955a48e7ae"}]}], "message_state": {"content": {"1": {"feedback": {"text": "the user must mention the type of report", "is_positive": False, "selected_categories": []}}}}}]]
    refine_with_chat_response = {
        "instruction": "**Role**\nYou are an agent that assists users in recording their working hours, vacations, or sick days based on their requests. Your primary goal is to accurately interpret the user's input and use the available tools to report the required information. \n\n**Key Responsibilities**\n- Identify the type of report the user wants to submit (working hours, vacation, or sick days)\n- Determine the relevant dates for the report\n- Use the available tools to retrieve and report the required information\n\n**Tool Usage Guidelines**\n1. Before you call a tool, ensure you have all the required parameters.\n2. Do not assume any tool parameters; instead, ask the user for clarification if necessary.\n3. Only pass parameters to the tool that are explicitly defined.\n4. Avoid calling the same tool multiple times with the same parameters.\n\n**How to Use Tools**\n- For working hours reports, use the get_current_month_working_days tool to retrieve working days, then use the get_expected_working_hours_per_day tool to get expected working hours for each day, and finally use the report_time_for_day tool to report the working hours.\n- For vacation or sick day reports, use the report_time_for_day tool with the corresponding report type.\n- If the user's request is unclear or incomplete, ask a clarification question to ensure you have the necessary information to fulfill their request. Examples of clarification questions include:\n  - Can you please specify the type of report you want to submit?\n  - What dates would you like to include in the report?\n  - Are there any specific details you would like to add to the report?\n\n**Best Practices**\n- Always confirm the user's request and the parameters for the report before calling any tools.\n- Provide clear and concise responses to the user, including any relevant details about the report.\n- If you are unsure about any aspect of the user's request, ask for clarification to ensure accuracy and completeness.",
        "score": None, "feedback": None}
    mock_get_all_threads_response = [
                {"id": "39d2f263-43d8-4356-ae70-69e54aeb547b", "tenant_id": "93dc9901-12a9-46ed-8d60-f2afc5e794b0",
                 "status": "ready", "tenant_name": "wxo-dev",
                 "title": "I need to report for all working days next week", "assistant_id": None,
                 "agent_id": "428277c5-6475-49b8-bad8-a0ff345418e5", "knowledge_base_id": None,
                 "created_by": "f242eadf-0dc9-4eae-b2d7-65b09b4b4b16", "created_by_username": "wxo.archer@ibm.com",
                 "created_on": "2025-08-21T08:22:06.916980Z", "updated_at": "2025-08-21T08:22:56.390068Z",
                 "deleted_at": None, "deleted_by": None},
                {"id": "bddb7839-0c24-48e4-9b5b-7a18a991908f", "tenant_id": "93dc9901-12a9-46ed-8d60-f2afc5e794b0",
                 "status": "ready", "tenant_name": "wxo-dev",
                 "title": "I need to report vacation for all working days next week", "assistant_id": None,
                 "agent_id": "428277c5-6475-49b8-bad8-a0ff345418e5", "knowledge_base_id": None,
                 "created_by": "f242eadf-0dc9-4eae-b2d7-65b09b4b4b16", "created_by_username": "wxo.archer@ibm.com",
                 "created_on": "2025-08-21T08:19:51.295355Z", "updated_at": "2025-08-21T08:20:01.125416Z",
                 "deleted_at": None, "deleted_by": None},
                {"id": "4f25414b-c665-4237-b8c8-70fd3b4acb68", "tenant_id": "93dc9901-12a9-46ed-8d60-f2afc5e794b0",
                 "status": "ready", "tenant_name": "wxo-dev", "title": "report a day off today", "assistant_id": None,
                 "agent_id": "428277c5-6475-49b8-bad8-a0ff345418e5", "knowledge_base_id": None,
                 "created_by": "f242eadf-0dc9-4eae-b2d7-65b09b4b4b16", "created_by_username": "wxo.archer@ibm.com",
                 "created_on": "2025-08-21T08:17:41.590951Z", "updated_at": "2025-08-21T08:17:48.829574Z",
                 "deleted_at": None, "deleted_by": None}]

    def test_refine_agent_with_chats(self):
        with (patch(
                "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.AgentsController.persist_record") as mock_persist_record, \
                patch("builtins.input") as mock_input, \
                patch(
                    "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.AgentsController.get_all_agents") as mock_get_all_agents, \
                patch(
                    "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.AgentsController.get_agent_by_id") as mock_get_agent, \
                patch(
                    "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.ThreadsClient.get_all_threads") as mock_get_all_threads, \
                patch(
                    "ibm_watsonx_orchestrate.client.threads.threads_client.ThreadsClient.get_threads_messages") as mock_get_threads_messages, \
                patch(
                    "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.get_cpe_client") as mock_get_cpe_client):

            mock_input.side_effect = ['1']
            mock_get_agent.return_value = Agent(name="dummy", description="dummy description", kind=AgentKind.NATIVE)
            mock_get_agent.return_value.instructions ="dummy instructions"
            mock_get_all_agents.return_value = {'test_agent': 123}
            mock_get_all_threads.return_value = self.mock_get_all_threads_response
            mock_get_cpe_client.return_value = MockCPEClient(refine_with_chat_response=self.refine_with_chat_response)
            mock_get_threads_messages.return_value = self.mock_get_threads_messages_response
            refine_agent_with_trajectories(
                output_file="test.yaml",
                agent_name="test_agent",
                dry_run_flag=False
            )
            mock_input.assert_called()
            mock_get_all_agents.assert_called()
            mock_get_all_threads.assert_called()
            mock_persist_record.assert_called()


    def test_refine_agent_with_chats_dry_run(self):
        with patch(
                "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.AgentsController.persist_record") as mock_persist_record, \
                patch("builtins.input") as mock_input, \
                patch(
                    "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.AgentsController.get_all_agents") as mock_get_all_agents, \
                patch(
                    "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.AgentsController.get_agent_by_id") as mock_get_agent, \
                patch(
                    "ibm_watsonx_orchestrate.client.threads.threads_client.ThreadsClient.get_all_threads") as mock_get_all_threads, \
                patch(
                    "ibm_watsonx_orchestrate.client.threads.threads_client.ThreadsClient.get_threads_messages") as mock_get_threads_messages, \
                patch(
                    "ibm_watsonx_orchestrate.cli.commands.copilot.copilot_controller.get_cpe_client") as mock_get_cpe_client:

            mock_input.side_effect = ['1']
            mock_get_agent.return_value = Agent(name="dummy", description="dummy description", kind=AgentKind.NATIVE)
            mock_get_agent.return_value.instructions = "dummy instructions"
            mock_get_all_agents.return_value = {'test_agent': 123}

            mock_get_all_threads.return_value = self.mock_get_all_threads_response
            mock_get_cpe_client.return_value = MockCPEClient(refine_with_chat_response=self.refine_with_chat_response)
            
            mock_get_threads_messages.return_value = self.mock_get_threads_messages_response
            
            refine_agent_with_trajectories(
                agent_name="test_agent",
                output_file=None,
                use_last_chat=False,
                dry_run_flag=True
            )
            mock_input.assert_called()
            mock_get_all_agents.assert_called()
            mock_get_all_threads.assert_called()
            mock_persist_record.assert_not_called()
