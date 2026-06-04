// Package build expone metadatos de compilación.
package build

// Version es la versión del binario. Se sobrescribe en el build con el flag
// -ldflags "-X .../internal/build.Version=vX.Y.Z".
var Version = "dev"
