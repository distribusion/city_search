{{- define "app.envs" -}}

{{- range $name, $value := .Values.app.env }}
- name: {{ $name }}
  value: {{ $value | quote }}
{{- end }}

{{- end }}

{{- define "app.envsSecret" -}}

  {{- range $name, $value := .Values.app.secretEnv }}
  {{ $name }}: {{ $value | b64enc | quote }}
  {{- end }}

{{- end }}
