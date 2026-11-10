#!/usr/bin/env python3
"""Generate the stable app_model interface for one validated model package."""

from __future__ import annotations

import argparse
from pathlib import Path

if __package__:
    from .model_package import ModelPackage, ModelPackageError, load_model_package
else:
    from model_package import ModelPackage, ModelPackageError, load_model_package


def render_adapter(model: ModelPackage) -> str:
    """Return deterministic C source for the package's generated runtime ABI."""

    return f"""/* SPDX-License-Identifier: Apache-2.0 */
/* Generated from {model.name}/model.json. Do not edit this build artifact. */

#include "app_model.h"

#include <{model.header.name}>

void {model.continuation_symbol}(void);

void app_model_reset(void)
{{
\t{model.completion_symbol} = 0;
}}

int32_t app_model_run(void *input, void *output)
{{
\tstruct {model.input_struct} inputs = {{
\t\t.{model.input.runtime_field} = input,
\t}};
\tstruct {model.output_struct} outputs = {{
\t\t.{model.output.runtime_field} = output,
\t}};

\treturn {model.entry_symbol}(&inputs, &outputs);
}}

bool app_model_is_finished(void)
{{
\treturn {model.completion_symbol} != 0;
}}

void app_model_continue(void)
{{
\t{model.continuation_symbol}();
}}
"""


def generate_adapter(model_directory: Path, output: Path) -> ModelPackage:
    """Validate a package and write its generated adapter to the build tree."""

    model = load_model_package(model_directory)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = output.with_suffix(f"{output.suffix}.tmp")
    temporary_output.write_text(render_adapter(model), encoding="utf-8")
    temporary_output.replace(output)
    return model


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model_directory", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        model = generate_adapter(args.model_directory, args.output)
    except (ModelPackageError, OSError) as error:
        parser.error(str(error))
    print(f"generated {args.output} for {model.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
