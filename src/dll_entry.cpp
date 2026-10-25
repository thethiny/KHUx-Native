// khux_game.dll's entry (KHUx-Native): khux.exe calls it after loading the DLL. The program's main is compiled as
// khux_program_main (build_game.py: -Dmain=khux_program_main).
int khux_program_main(int argc, char **argv);
extern "C" __declspec(dllexport) int khux_main(int argc, char **argv) { return khux_program_main(argc, argv); }
