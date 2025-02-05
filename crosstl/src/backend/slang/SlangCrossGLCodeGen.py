from .SlangAst import *
from .SlangParser import *
from .SlangLexer import *


class SlangToCrossGLConverter:
    def __init__(self):
        self.vertex_inputs = []
        self.vertex_outputs = []
        self.fragment_inputs = []
        self.fragment_outputs = []
        self.cbuffers = []
        self.type_map = {
            "void": "void",
            "float2": "vec2",
            "float3": "vec3",
            "float4": "vec4",
            "float2x2": "mat2",
            "float3x3": "mat3",
            "float4x4": "mat4",
            "int": "int",
            "int2": "ivec2",
            "int3": "ivec3",
            "int4": "ivec4",
            "uint": "uint",
            "uint2": "uvec2",
            "uint3": "uvec3",
            "uint4": "uvec4",
            "bool": "bool",
            "bool2": "bvec2",
            "bool3": "bvec3",
            "bool4": "bvec4",
            "float": "float",
            "double": "double",
            "Texture2D": "sampler2D",
            "TextureCube": "samplerCube",
        }

    def generate(self, ast):
        self.process_structs(ast)
        code = "shader main {\n"
        if ast.imports:
            code += "    // Imports\n"
            for imp in ast.imports:
                code += f"    import {imp.module_name};\n"
            code += "\n"
        if ast.exports:
            code += "    // Exports\n"
            for exp in ast.exports:
                code += f"    export {exp.item};\n"
            code += "\n"
        # Generate custom types
        for node in ast.typedefs:
            code += (
                f"    typedef {self.map_type(node.original_type)} {node.new_type};\n"
            )
        # Generate custom structs
        for node in ast.structs:
            if isinstance(node, StructNode):
                code += f"    struct {node.name} {{\n"
                for member in node.members:
                    code += f"        {self.map_type(member.vtype)} {member.name};\n"
                code += "    }\n"
        # Generate global variables
        for node in ast.global_vars:
            code += f"    {self.map_type(node.vtype)} {node.name};\n"
        # Generate cbuffers
        if ast.cbuffers:
            code += "    // Constant Buffers\n"
            code += self.generate_cbuffers(ast)

        # Generate custom functions
        for func in ast.functions:
            function_type_node = func.type_function
            if function_type_node == "custom":
                code += self.generate_function(func)
            else:
                if function_type_node.vertex:
                    code += f"vertex {{\n"
                    code += self.generate_function(func)
                    code += f"}}\n"
                elif function_type_node.fragment:
                    code += f"fragment {{\n"
                    code += self.generate_function(func)
                    code += f"}}\n"
                elif function_type_node.compute:
                    code += f"compute {{\n"
                    code += self.generate_function(func)
                    code += f"}}\n"

        code += "}\n"
        return code

    def process_structs(self, ast):
        for node in ast.structs:
            if isinstance(node, StructNode):
                if node.name == "VSInput":
                    for member in node.members:
                        self.vertex_inputs.append(
                            (self.map_type(member.vtype), member.name)
                        )
                elif node.name == "VSOutput":
                    for member in node.members:
                        if member.name != "position":
                            self.vertex_outputs.append(
                                (self.map_type(member.vtype), member.name)
                            )
                elif node.name == "PSInput":
                    for member in node.members:
                        self.fragment_inputs.append(
                            (self.map_type(member.vtype), member.name)
                        )
                elif node.name == "PSOUTPUT":
                    for member in node.members:
                        self.fragment_outputs.append(
                            (self.map_type(member.vtype), member.name)
                        )

    def generate_cbuffers(self, ast):
        code = ""
        for node in ast.cbuffers:
            if isinstance(node, StructNode):
                code += f"    cbuffer {node.name} {{\n"
                for member in node.members:
                    code += f"        {self.map_type(member.vtype)} {member.name};\n"
                code += "    }\n"
        return code

    def generate_io_declarations(self, shader_type):
        code = ""
        if shader_type == "vertex":
            for type, name in self.vertex_inputs:
                code += f"        input {self.map_type(type)} {name};\n"
            for type, name in self.vertex_outputs:
                code += f"        output {self.map_type(type)} {name};\n"
        elif shader_type == "fragment":
            for type, name in self.fragment_inputs:
                code += f"        input {self.map_type(type)} {name};\n"
            for type, name in self.fragment_outputs:
                code += f"        output {self.map_type(type)} {name};\n"
        return code.rstrip()

    def generate_function(self, func):
        params = ", ".join(f"{self.map_type(p.vtype)} {p.name}" for p in func.params)
        code = f"    {self.map_type(func.return_type)} {func.name}({params}) {{\n"
        code += self.generate_function_body(func.body, indent=2)
        code += "    }\n\n"
        return code

    def generate_vertex_main(self, func):
        code = "        void main() {\n"
        code += self.generate_function_body(func.body, indent=3, is_main=True)
        code += "        }\n"
        return code

    def generate_fragment_main(self, func):
        code = "        void main() {\n"
        code += self.generate_function_body(func.body, indent=3, is_main=True)
        code += "        }\n"
        return code

    def generate_function_body(self, body, indent=0, is_main=False):
        code = ""
        for stmt in body:
            code += "    " * indent
            if isinstance(stmt, VariableNode):
                code += f"{self.map_type(stmt.vtype)} {stmt.name};\n"
            elif isinstance(stmt, AssignmentNode):
                code += self.generate_assignment(stmt, is_main) + ";\n"
            elif isinstance(stmt, BinaryOpNode):
                code += f"{self.generate_expression(stmt.left, is_main)} {stmt.op} {self.generate_expression(stmt.right, is_main)};\n"
            elif isinstance(stmt, ReturnNode):
                if not is_main:
                    code += f"return {self.generate_expression(stmt.value, is_main)};\n"
            elif isinstance(stmt, ForNode):
                code += self.generate_for_loop(stmt, indent, is_main)
            elif isinstance(stmt, IfNode):
                code += self.generate_if_statement(stmt, indent, is_main)
        return code

    def generate_for_loop(self, node, indent, is_main):
        init = self.generate_expression(node.init, is_main)
        condition = self.generate_expression(node.condition, is_main)
        update = self.generate_expression(node.update, is_main)

        code = f"for ({init}; {condition}; {update}) {{\n"
        code += self.generate_function_body(node.body, indent + 1, is_main)
        code += "    " * indent + "}\n"
        return code

    def generate_if_statement(self, node, indent, is_main):
        condition = self.generate_expression(node.condition, is_main)

        code = f"if ({condition}) {{\n"
        code += self.generate_function_body(node.if_body, indent + 1, is_main)
        code += "    " * indent + "}"

        if node.else_body:
            if isinstance(node.else_body, IfNode):
                code += " else "
                code += self.generate_if_statement(node.else_body, indent, is_main)
            else:
                code += " else {\n"
                code += self.generate_function_body(node.else_body, indent + 1, is_main)
                code += "    " * indent + "}"

        code += "\n"
        return code

    def generate_assignment(self, node, is_main):
        lhs = self.generate_expression(node.left, is_main)
        rhs = self.generate_expression(node.right, is_main)
        if (
            is_main
            and isinstance(node.left, MemberAccessNode)
            and node.left.object == "output"
        ):
            if node.left.member == "position":
                return f"gl_Position = {rhs}"
            return f"{node.left.member} = {rhs}"
        return f"{lhs} = {rhs}"

    def generate_expression(self, expr, is_main=False):
        if isinstance(expr, str):
            return expr
        elif isinstance(expr, VariableNode):
            return f"{self.map_type(expr.vtype)} {expr.name}"
        elif isinstance(expr, BinaryOpNode):
            left = self.generate_expression(expr.left, is_main)
            right = self.generate_expression(expr.right, is_main)
            return f"{left} {expr.op} {right}"
        elif isinstance(expr, AssignmentNode):
            left = self.generate_expression(expr.left, is_main)
            right = self.generate_expression(expr.right, is_main)
            return f"{left} {expr.operator} {right}"
        elif isinstance(expr, UnaryOpNode):
            operand = self.generate_expression(expr.operand, is_main)
            return f"{expr.op}{operand}"
        elif isinstance(expr, FunctionCallNode):
            args = ", ".join(
                self.generate_expression(arg, is_main) for arg in expr.args
            )
            return f"{expr.name}({args})"
        elif isinstance(expr, MemberAccessNode):
            obj = self.generate_expression(expr.object)
            if obj == "output" or obj == "input":
                return expr.member
            return f"{obj}.{expr.member}"
        elif isinstance(expr, TernaryOpNode):
            return f"{self.generate_expression(expr.condition, is_main)} ? {self.generate_expression(expr.true_expr, is_main)} : {self.generate_expression(expr.false_expr, is_main)}"
        elif isinstance(expr, VectorConstructorNode):
            args = ", ".join(
                self.generate_expression(arg, is_main) for arg in expr.args
            )
            return f"{self.map_type(expr.type_name)}({args})"
        else:
            return str(expr)

    def map_type(self, slang_type):
        if slang_type:
            return self.type_map.get(slang_type, slang_type)
        return slang_type
