import automation_routines

auto_routine_dict = automation_routines.get_automation_routines()
print(auto_routine_dict)

auto_routine_dict["test_auto"].run()