package collect

import "errors"

// shortRunnerErr summarizes a run.Result error to a short hint. The
// full error may include the full lxc path or the binary path, which
// we do not want to leak in dimension Detail (operator-facing).
func shortRunnerErr(err error) error {
	if err == nil {
		return nil
	}
	return errors.New("runner failed")
}
