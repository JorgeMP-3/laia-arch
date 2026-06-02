package state

import "time"

// SchemaVersion del status.json. Subir cuando cambie el formato (un lector con
// schema menor puede avisar en vez de malinterpretar campos).
const SchemaVersion = 1

// StatusFile es el nombre canónico del snapshot dentro del dir de estado.
const StatusFile = "status.json"

// Status es el snapshot que el daemon publica cada tick y que `laia-res status`
// lee. En S0 es solo un heartbeat; S1+ añadirá las dimensiones vigiladas
// (egress, RAM, VRAM, disco, prod-viva) bajo un campo Dimensions.
type Status struct {
	Schema    int       `json:"schema"`
	Version   string    `json:"version"`
	Mode      string    `json:"mode"` // monitor | enforce (v1: siempre monitor)
	Host      string    `json:"host"`
	PID       int       `json:"pid"`
	StartedAt time.Time `json:"started_at"`
	UpdatedAt time.Time `json:"updated_at"`
	Tick      uint64    `json:"tick"`
}
