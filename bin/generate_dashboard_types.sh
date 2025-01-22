#!/bin/bash
set -eu

DIR="$(cd $(dirname "$0") && pwd)"

main() {
    if [[ "$1" == "--help" ]]; then
        echo "Generates dashboard/src/http_types.ts from gpsreceiver/gpsreceiver/http_types.py"
        exit
    fi
    
    # Create a temporary file to store the JSON schema.
    local schema_path
    schema_path="$(mktemp)"
    trap 'rm -f "'"${schema_path}"'"' EXIT

    # Generate a JSON schema from the Python types.
    #
    # We want to suppress the titles of fields so json-schema-to-typescript
    # doesn't generate a bunch of random types that are just used for fields.
    cd "${DIR}/../gpsreceiver"
    source .env/bin/activate
    python - <<EOF > "${schema_path}"
from gpsreceiver.http_types import HttpData
from json import dumps
from pydantic.json_schema import GenerateJsonSchema

class TitleSuppressingGenerateJsonSchema(GenerateJsonSchema):
    def field_title_should_be_set(self, schema):
        return False

print(dumps(HttpData.model_json_schema(schema_generator=TitleSuppressingGenerateJsonSchema)))
EOF

    # Generate the TypeScript types from the JSON schema.
    cd "${DIR}/../dashboard"
    node - <<EOF > src/http_types.ts
import { compileFromFile } from "json-schema-to-typescript";

compileFromFile(
    "${schema_path}",
    {
        additionalProperties: false,
        bannerComment: "/**\n * This file was automatically generated. Don't edit it by hand. Instead, change\n * gpsreceiver/gpsreceiver/http_types.py and run bin/generate_dashboard_types.sh.\n */"
    }
).then(console.log)
EOF
}

main "$@"