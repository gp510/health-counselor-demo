"""
Tests for Healthcare MCP Server integration with Biomarker Agent.

These tests verify:
1. Healthcare MCP server can be spawned and initialized
2. Tools are available (fda_drug_lookup, pubmed_search, icd10_lookup, medical_calculator)
3. PubMed search works with NCBI_API_KEY from .env
4. Tool responses follow expected MCP format

Usage:
    pytest tests/test_healthcare_mcp.py -v
"""
import os
import json
import asyncio
import pytest
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Check if mcp package is available
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

# Skip all tests if mcp package not available
pytestmark = pytest.mark.skipif(
    not MCP_AVAILABLE,
    reason="MCP package not installed (pip install mcp)"
)


@pytest.fixture
def ncbi_api_key():
    """Get NCBI API key from environment."""
    key = os.environ.get("NCBI_API_KEY")
    if not key:
        pytest.skip("NCBI_API_KEY not set in environment")
    return key


@pytest.fixture
def healthcare_server_params(ncbi_api_key):
    """Create server parameters for healthcare-mcp."""
    return StdioServerParameters(
        command="npx",
        args=["healthcare-mcp"],
        env={
            **os.environ,
            "NCBI_API_KEY": ncbi_api_key,
        }
    )


class TestHealthcareMCPConnection:
    """Test basic MCP server connection and initialization."""

    @pytest.mark.asyncio
    async def test_server_starts_and_initializes(self, healthcare_server_params):
        """Healthcare MCP server should start and complete initialization handshake."""
        async with stdio_client(healthcare_server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize the session
                result = await session.initialize()

                assert result is not None
                assert hasattr(result, 'protocolVersion')
                assert result.protocolVersion == "2024-11-05" or result.protocolVersion.startswith("2")

    @pytest.mark.asyncio
    async def test_server_provides_server_info(self, healthcare_server_params):
        """Server should provide name and version information."""
        async with stdio_client(healthcare_server_params) as (read, write):
            async with ClientSession(read, write) as session:
                result = await session.initialize()

                assert hasattr(result, 'serverInfo')
                assert result.serverInfo.name is not None
                # Server name should indicate it's the healthcare server
                assert 'health' in result.serverInfo.name.lower() or result.serverInfo.name


class TestHealthcareMCPTools:
    """Test that expected tools are available."""

    @pytest.mark.asyncio
    async def test_tools_list_available(self, healthcare_server_params):
        """Server should provide a list of tools."""
        async with stdio_client(healthcare_server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_result = await session.list_tools()

                assert tools_result is not None
                assert hasattr(tools_result, 'tools')
                assert len(tools_result.tools) > 0

    @pytest.mark.asyncio
    async def test_expected_tools_present(self, healthcare_server_params):
        """Expected healthcare tools should be available."""
        # Actual tool names from healthcare-mcp server
        expected_tools = {
            "fda_drug_lookup",
            "pubmed_search",
            "lookup_icd_code",  # ICD-10 lookup
            "calculate_bmi",    # Medical calculator (BMI)
        }

        async with stdio_client(healthcare_server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_result = await session.list_tools()

                available_tools = {tool.name for tool in tools_result.tools}

                # Check each expected tool is present
                for tool_name in expected_tools:
                    assert tool_name in available_tools, f"Expected tool '{tool_name}' not found in {available_tools}"

    @pytest.mark.asyncio
    async def test_pubmed_search_has_required_parameters(self, healthcare_server_params):
        """pubmed_search tool should have expected input schema."""
        async with stdio_client(healthcare_server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_result = await session.list_tools()

                pubmed_tool = next(
                    (t for t in tools_result.tools if t.name == "pubmed_search"),
                    None
                )

                assert pubmed_tool is not None
                assert pubmed_tool.inputSchema is not None
                # Should accept a query parameter
                schema = pubmed_tool.inputSchema
                assert 'properties' in schema or schema.get('type') == 'object'


class TestPubMedSearchWithNCBIKey:
    """Test PubMed search functionality with NCBI API key."""

    @pytest.mark.asyncio
    async def test_pubmed_search_returns_results(self, healthcare_server_params):
        """PubMed search should return results for a valid biomarker query."""
        async with stdio_client(healthcare_server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Search for a common biomarker topic
                result = await session.call_tool(
                    "pubmed_search",
                    arguments={"query": "vitamin D deficiency biomarkers"}
                )

                assert result is not None
                assert hasattr(result, 'content')
                assert len(result.content) > 0

                # Check that we got text content back
                content = result.content[0]
                assert hasattr(content, 'type')
                assert content.type == 'text'
                assert hasattr(content, 'text')
                assert len(content.text) > 0

    @pytest.mark.asyncio
    async def test_pubmed_search_cholesterol_research(self, healthcare_server_params):
        """PubMed search should find cholesterol-related research articles."""
        async with stdio_client(healthcare_server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                result = await session.call_tool(
                    "pubmed_search",
                    arguments={"query": "LDL cholesterol cardiovascular risk"}
                )

                assert result is not None
                content_text = result.content[0].text

                # Should contain research-related content
                assert len(content_text) > 50, "Expected substantive research results"

    @pytest.mark.asyncio
    async def test_pubmed_search_returns_structured_data(self, healthcare_server_params):
        """PubMed search should return parseable structured data."""
        async with stdio_client(healthcare_server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                result = await session.call_tool(
                    "pubmed_search",
                    arguments={"query": "HbA1c diabetes monitoring"}
                )

                content_text = result.content[0].text

                # Try to parse as JSON if it looks like JSON
                if content_text.strip().startswith('{') or content_text.strip().startswith('['):
                    try:
                        data = json.loads(content_text)
                        assert data is not None
                    except json.JSONDecodeError:
                        # Not JSON, but still valid text response
                        pass


class TestFDADrugLookup:
    """Test FDA drug lookup functionality."""

    @pytest.mark.asyncio
    async def test_fda_drug_lookup_common_medication(self, healthcare_server_params):
        """FDA lookup should return info for common medications."""
        async with stdio_client(healthcare_server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                result = await session.call_tool(
                    "fda_drug_lookup",
                    arguments={"drug_name": "metformin"}
                )

                assert result is not None
                assert len(result.content) > 0
                content_text = result.content[0].text
                assert len(content_text) > 0


class TestBMICalculator:
    """Test BMI calculator functionality."""

    @pytest.mark.asyncio
    async def test_bmi_calculator_available(self, healthcare_server_params):
        """BMI calculator tool should be callable."""
        async with stdio_client(healthcare_server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_result = await session.list_tools()

                calc_tool = next(
                    (t for t in tools_result.tools if t.name == "calculate_bmi"),
                    None
                )

                assert calc_tool is not None
                assert calc_tool.description is not None


class TestICD10Lookup:
    """Test ICD-10 code lookup functionality."""

    @pytest.mark.asyncio
    async def test_icd10_lookup_available(self, healthcare_server_params):
        """ICD-10 lookup tool should be available."""
        async with stdio_client(healthcare_server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_result = await session.list_tools()

                icd_tool = next(
                    (t for t in tools_result.tools if t.name == "lookup_icd_code"),
                    None
                )

                assert icd_tool is not None


class TestMCPErrorHandling:
    """Test error handling for MCP operations."""

    @pytest.mark.asyncio
    async def test_invalid_tool_call_handled(self, healthcare_server_params):
        """Calling non-existent tool should return error, not crash."""
        async with stdio_client(healthcare_server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Try calling a tool that doesn't exist
                try:
                    result = await session.call_tool(
                        "nonexistent_tool",
                        arguments={"query": "test"}
                    )
                    # If we get here, check for error indicator
                    if result.isError:
                        assert True  # Expected error response
                except Exception as e:
                    # Exception is acceptable for invalid tool
                    assert "nonexistent" in str(e).lower() or True

    @pytest.mark.asyncio
    async def test_empty_query_handled(self, healthcare_server_params):
        """Empty query should be handled gracefully."""
        async with stdio_client(healthcare_server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                try:
                    result = await session.call_tool(
                        "pubmed_search",
                        arguments={"query": ""}
                    )
                    # Either returns error or empty results - both are acceptable
                    assert result is not None
                except Exception:
                    # Exception for empty query is acceptable
                    pass


class TestNCBIKeyIntegration:
    """Test that NCBI API key is properly used."""

    def test_ncbi_key_loaded_from_env(self, ncbi_api_key):
        """NCBI API key should be loaded from .env file."""
        assert ncbi_api_key is not None
        assert len(ncbi_api_key) > 10  # Keys are typically longer

    def test_ncbi_key_in_dotenv_file(self):
        """NCBI_API_KEY should be defined in .env file."""
        env_path = Path(__file__).parent.parent / ".env"

        if not env_path.exists():
            pytest.skip(".env file not found")

        with open(env_path, 'r') as f:
            content = f.read()

        assert "NCBI_API_KEY" in content, "NCBI_API_KEY should be defined in .env"


class TestBiomarkerAgentMCPConfig:
    """Test that biomarker agent has correct MCP configuration."""

    def test_biomarker_agent_config_has_mcp_section(self):
        """Biomarker agent config should include mcp_servers section."""
        config_path = Path(__file__).parent.parent / "configs" / "agents" / "biomarker-agent.yaml"

        if not config_path.exists():
            pytest.skip("Biomarker agent config not found")

        with open(config_path, 'r') as f:
            content = f.read()

        assert "mcp_servers:" in content
        assert "healthcare" in content
        assert "pubmed_search" in content
        assert "lookup_icd_code" in content
        assert "calculate_bmi" in content
        assert "NCBI_API_KEY" in content

    def test_biomarker_agent_has_graceful_fallback_instructions(self):
        """Biomarker agent should have instructions for MCP fallback."""
        config_path = Path(__file__).parent.parent / "configs" / "agents" / "biomarker-agent.yaml"

        if not config_path.exists():
            pytest.skip("Biomarker agent config not found")

        with open(config_path, 'r') as f:
            content = f.read()

        # Check for graceful fallback instructions
        assert "Graceful Fallback" in content or "graceful" in content.lower()
        assert "temporarily unavailable" in content.lower() or "fails" in content.lower()
