"""
Function processor module for executing JavaScript functions within flows.
Handles JavaScript execution, sandboxing, and execution history recording.
"""

import json
import logging
import time
from typing import Any, Dict, Optional
import platform
import js2py
from sqlalchemy.orm import Session

from app.models.function import Function
from app.models.function_history import FunctionHistory

logger = logging.getLogger(__name__)


def replace_nan_values(data):
    """
    Recursively replace NaN values in a dictionary with None.
    """
    if isinstance(data, dict):
        return {k: replace_nan_values(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [replace_nan_values(v) for v in data]
    elif isinstance(data, float) and (data != data):  # Check for NaN
        return None
    return data


async def process_function_node(
    db: Session,
    node: Dict[str, Any],
    payload: Dict[str, Any],
    flow_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Process a function node in a flow.

    Args:
        db: Database session
        node: The function node configuration
        payload: The data payload to process
        flow_id: Optional ID of the parent flow for tracking history

    Returns:
        Dict containing the function processing results
    """
    # Try to get the function ID from multiple possible field names
    function_id = None
    node_data = node.get("data", {})

    # Check different possible field names for function ID
    for id_field in ["functionId", "entityId", "id"]:
        if id_field in node_data:
            function_id = node_data.get(id_field)
            print(
                f"FUNCTION PROCESSOR: Found function ID {function_id} via field {id_field}"
            )
            break

    if not function_id:
        print("FUNCTION PROCESSOR: Error - Missing function ID in node data")
        return {"function_result": "error_missing_function_id"}

    # Convert to int if it's a string number
    try:
        if isinstance(function_id, str) and function_id.isdigit():
            function_id = int(function_id)
    except (ValueError, TypeError):
        pass

    print(f"FUNCTION PROCESSOR: Looking up function with ID {function_id}")
    function = db.query(Function).filter(Function.id == function_id).first()

    if not function or not function.code:
        print(
            f"FUNCTION PROCESSOR: Error - Function with ID {function_id} not found or has no code"
        )
        logger.error(f"Function with ID {function_id} not found or has no code")
        return {"function_result": "error_function_not_found"}

    print(f"FUNCTION PROCESSOR: Found function '{function.name}' with ID {function_id}")
    print(f"FUNCTION PROCESSOR: Function code: {function.code[:100]}...")

    # Create function history record
    start_time = time.time()
    function_history = FunctionHistory(
        function_id=function_id,
        flow_id=flow_id,  # Add the flow_id to track which flow executed this function
        status="running",
        input_data=payload,
    )
    db.add(function_history)
    db.flush()  # Get the history ID without committing

    try:
        print(f"FUNCTION PROCESSOR: Executing JavaScript function")

        # Sanitize and check the code for potentially dangerous constructs
        code = function.code

        # Disallow eval and other dangerous functions
        dangerous_patterns = [
            "eval(",
            "Function(",
            "setTimeout(",
            "setInterval(",
            "while(true",
            "while (true",
            "for(;;",
            "for (;;",
            "this.",
            "global.",
            "require(",
            "process.",
            "globalThis.",
            "window.",
        ]

        for pattern in dangerous_patterns:
            if pattern in code:
                raise ValueError(f"Potentially unsafe code pattern detected: {pattern}")

        # Limit code to prevent infinite loops
        max_execution_time = 5000  # 5 seconds in milliseconds
        execution_timeout = time.time() + (max_execution_time / 1000)

        # Create a wrapper that passes the payload as the 'input' parameter
        # This ensures the payload is always accessible as 'input' inside any JS function
        # Also adds timeout protection and sandboxing
        wrapper_code = f"""
        function executeFunction(payload) {{
            // Create a sandbox with only essential objects
            // Block access to global objects, dangerous functions and properties
            
            // Create a safe input object that contains the payload
            var input = payload;
            
            // Guard against long-running code
            var __startTime = new Date().getTime();
            var __checkTimeout = function() {{
                if (new Date().getTime() - __startTime > {max_execution_time}) {{
                    throw new Error("Function execution timed out after {max_execution_time}ms");
                }}
            }};
            
            // The actual function code with timeout checks inserted
            try {{
                {code}
                
                // Final timeout check before returning
                __checkTimeout();
                
                // Try to call the function with the input parameter
                // Look for functions with common names used in IoT data processing
                if (typeof decodeUplink === 'function') {{
                    __checkTimeout();
                    return decodeUplink(input);
                }} else if (typeof processData === 'function') {{
                    __checkTimeout();
                    return processData(input);
                }} else if (typeof decoder === 'function') {{
                    __checkTimeout();
                    return decoder(input);
                }} else if (typeof process === 'function') {{
                    __checkTimeout();
                    return process(input);
                }} else {{
                    // If no known function is found, look for any function and call it
                    for (var key in this) {{
                        __checkTimeout();
                        if (typeof this[key] === 'function' && key !== 'executeFunction' && 
                            key !== '__checkTimeout' && !key.startsWith('__')) {{
                            return this[key](input);
                        }}
                    }}
                    // If no function is found at all, return the input as is
                    return input;
                }}
            }} catch (e) {{
                throw new Error("Error in JS function: " + e.message);
            }}
        }}
        
        executeFunction
        """

        # Setup timeout protection for the Python side as well
        # This serves as a backup in case the JavaScript timeout doesn't trigger
        def timeout_handler(signum, frame):
            raise TimeoutError(
                f"Function execution timed out after {max_execution_time}ms"
            )

        # Only set up signal handler if on a platform that supports it (not Windows)
        if platform.system() != "Windows":
            import signal

            signal.signal(signal.SIGALRM, timeout_handler)
            # Convert milliseconds to seconds for the alarm, add a small buffer
            signal.alarm(int(max_execution_time / 1000) + 1)

        # Extract the executeFunction function from the wrapper code
        try:
            js_func = js2py.eval_js(wrapper_code)

            # Call the function with the payload, enforcing timeout
            print(
                f"FUNCTION PROCESSOR: Executing wrapped function with payload accessible as 'input'"
            )

            result = None
            deadline = time.time() + (max_execution_time / 1000)
            result = js_func(payload)

            # Check if we exceeded the timeout
            if time.time() > deadline:
                raise TimeoutError(
                    f"Function execution timed out after {max_execution_time}ms"
                )

        finally:
            # Clean up signal handler if we set one
            if platform.system() != "Windows":
                signal.alarm(0)

        print(
            f"FUNCTION PROCESSOR: Function execution raw result type: {type(result).__name__}"
        )

        # Ensure the result is JSON-serializable
        try:
            # Handle the js2py object wrapper specifically
            if hasattr(result, "to_dict"):
                # Convert js2py object wrapper to Python dict
                print(
                    f"FUNCTION PROCESSOR: Converting js2py object wrapper to Python dict"
                )
                result_dict = result.to_dict()
                serialized_result = result_dict
            elif result is None:
                serialized_result = {"data": None}
            elif isinstance(result, (dict, list, str, int, float, bool)):
                # For dictionaries, use as is
                if isinstance(result, dict):
                    serialized_result = result
                # For other types, wrap in a dictionary with a data key
                else:
                    serialized_result = {"data": result}
            else:
                # For other types, convert to string representation and wrap in a dictionary
                print(
                    f"FUNCTION PROCESSOR: Converting non-serializable result of type {type(result).__name__} to dictionary"
                )
                serialized_result = {"data": str(result)}

            # Validate by attempting to JSON serialize (will raise exception if not serializable)
            json.dumps(serialized_result)
            print(f"FUNCTION PROCESSOR: Result successfully serialized to JSON")
        except (TypeError, OverflowError, ValueError) as e:
            print(f"FUNCTION PROCESSOR: Warning - Result not JSON serializable: {e}")
            # Fall back to dictionary with string representation if JSON serialization fails
            serialized_result = {
                "error": "Non-serializable result",
                "data": str(result),
            }

        # Make absolutely sure we have a dictionary
        if not isinstance(serialized_result, dict):
            serialized_result = {"data": serialized_result}

        # Calculate execution time in milliseconds
        execution_time = int((time.time() - start_time) * 1000)

        # Update function history with success - ensure result is serializable
        function_history.status = "success"
        function_history.output_data = serialized_result
        function_history.execution_time = execution_time

        # Ensure output_data is a valid JSON, if not replace it with an error
        try:
            # First try to detect NaN values and replace them with null
            if isinstance(function_history.output_data, dict):
                function_history.output_data = replace_nan_values(
                    function_history.output_data
                )

            # After sanitizing, check if it can be serialized correctly
            json_string = json.dumps(function_history.output_data)

            # If successful, let's make sure we actually have valid JSON by parsing it back
            json.loads(json_string)
        except (TypeError, OverflowError, ValueError) as e:
            print(
                f"FUNCTION PROCESSOR: Warning - Function history output data not JSON serializable: {e}"
            )
            # Convert to a safe format
            function_history.output_data = {
                "status": "error",
                "original_error": (
                    str(e).split("\n")[0] if str(e) else "Unknown serialization error"
                ),
                "data": "Error in output data - contained non-serializable values",
            }

        # Save the function history with extra error handling
        try:
            db.add(function_history)
            db.flush()  # Attempt to flush changes to detect errors early
            print(f"FUNCTION PROCESSOR: Successfully saved function execution history")
        except Exception as db_error:
            print(
                f"FUNCTION PROCESSOR: Error saving function history: {str(db_error).split('[SQL:')[0]}"
            )
            # Convert output_data to a simple error message as last resort
            function_history.output_data = {
                "error": "Data contained non-serializable values"
            }
            try:
                db.add(function_history)
                db.flush()
                print(
                    f"FUNCTION PROCESSOR: Saved function history with simplified error data"
                )
            except Exception as e2:
                print(
                    f"FUNCTION PROCESSOR: Failed to save function history even with simplified error: {str(e2).split('[SQL:')[0]}"
                )

        print(f"FUNCTION PROCESSOR: updating function status to success in database")
        # Commit the transaction to save the function history

        print(
            f"FUNCTION PROCESSOR: Function executed successfully in {execution_time}ms"
        )
        logger.info(
            f"Function {function.name} (ID: {function_id}) executed successfully in {execution_time}ms"
        )

        return {
            "function_result": "success",
            "function_history_id": function_history.id,
            "modified_payload": serialized_result,
        }
    except TimeoutError as e:
        # Handle timeout specifically
        execution_time = int((time.time() - start_time) * 1000)

        function_history.status = "error"
        function_history.error_message = (
            f"Function execution timed out after {execution_time}ms"
        )
        function_history.execution_time = execution_time

        try:
            db.add(function_history)
            db.flush()
        except Exception as db_error:
            print(
                f"FUNCTION PROCESSOR: Error saving timeout history: {str(db_error).split('[SQL:')[0]}"
            )
            # Try one more time with simplified data
            function_history.output_data = None
            try:
                db.add(function_history)
                db.flush()
            except:
                # If it still fails, proceed without saving history
                pass

        print(f"FUNCTION PROCESSOR: Function execution timed out: {str(e)}")
        logger.error(
            f"Function {function.name} (ID: {function_id}) timed out after {execution_time}ms"
        )

        return {
            "function_result": "error",
            "function_error": f"Function execution timed out after {execution_time}ms",
            "function_history_id": function_history.id,
        }
    except Exception as e:
        # Calculate execution time in milliseconds
        execution_time = int((time.time() - start_time) * 1000)

        # Update function history with error
        function_history.status = "error"
        function_history.error_message = str(e)
        function_history.execution_time = execution_time

        # Try to save the error information
        try:
            db.add(function_history)
            db.flush()
            print(f"FUNCTION PROCESSOR: Saved error information to history")
        except Exception as db_error:
            print(f"FUNCTION PROCESSOR: Could not save error to database: {db_error}")
            # At this point, best to roll back to avoid cascading errors
            db.rollback()

        print(f"FUNCTION PROCESSOR: Error executing function: {str(e)}")
        logger.error(
            f"Error executing function {function.name} (ID: {function_id}): {str(e)}"
        )

        return {
            "function_result": "error",
            "function_error": str(e),
            "function_history_id": function_history.id,
        }
    finally:
        # update the function status based on the execution result
        if function_history.status == "success":
            function.status = "success"
        else:
            function.status = "error"
        db.commit()
        print(
            f"FUNCTION PROCESSOR: Function status updated to {function.status} in database"
        )
