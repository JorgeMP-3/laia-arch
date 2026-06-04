// Package state — lectura/escritura atómica del estado del daemon en disco.
//
// El estado vive en /srv/laia/state/resourced/ y lo consume `laia-res` sin
// necesidad de que el daemon esté vivo. La escritura es atómica (tmp + rename)
// para que un lector nunca vea un fichero a medias aunque el daemon muera
// escribiendo — el daemon es stateless entre ticks (recalcula desde cero), así
// que un estado a medias nunca corrompe nada.
package state

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

// DefaultDir es el directorio de estado por defecto.
const DefaultDir = "/srv/laia/state/resourced"

// WriteJSON escribe v como JSON indentado a dir/name de forma atómica
// (CreateTemp en el mismo dir + Rename), creando dir si no existe. El rename es
// atómico dentro del mismo filesystem.
func WriteJSON(dir, name string, v any) error {
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return fmt.Errorf("mkdir %s: %w", dir, err)
	}
	data, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal: %w", err)
	}
	data = append(data, '\n')

	tmp, err := os.CreateTemp(dir, name+".tmp-*")
	if err != nil {
		return fmt.Errorf("createtemp: %w", err)
	}
	tmpName := tmp.Name()
	defer os.Remove(tmpName) // no-op si el rename tuvo éxito

	if _, err := tmp.Write(data); err != nil {
		tmp.Close()
		return fmt.Errorf("write: %w", err)
	}
	if err := tmp.Chmod(0o644); err != nil {
		tmp.Close()
		return fmt.Errorf("chmod: %w", err)
	}
	if err := tmp.Close(); err != nil {
		return fmt.Errorf("close: %w", err)
	}
	if err := os.Rename(tmpName, filepath.Join(dir, name)); err != nil {
		return fmt.Errorf("rename: %w", err)
	}
	return nil
}

// ReadJSON lee path y lo deserializa en v. Devuelve un error que satisface
// os.IsNotExist si el fichero no existe (el llamante distingue "aún no hay
// estado" de un error real).
func ReadJSON(path string, v any) error {
	data, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	return json.Unmarshal(data, v)
}
