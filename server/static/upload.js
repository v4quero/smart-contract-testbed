function updateSubmitButton() {
    clearSession();
    const noFileSelected = document.getElementById('file').value < 1;

    const inputs = document.getElementsByTagName('input');

    let noCheckboxChecked = true;
    for(let i=0; i<inputs.length; i++){
        if (inputs[i].type.toLowerCase() === 'checkbox'){
            if(inputs[i].checked){
                noCheckboxChecked=false;
            }
        }
    }
    document.getElementById('submit').disabled = noFileSelected || noCheckboxChecked || document.getElementById('file').length === 0;
}

function updateAvailableTools(bytecode_incompatible_tool_names) {
    const extension = getExtension()
    let bytecode = false;
    if(extension === '.bin' || extension==='.hex'){
        bytecode=true;
    }
    for(const tool_name of bytecode_incompatible_tool_names){
        const elements = document.getElementsByClassName(tool_name);
        for(let i=0; i<elements.length; i++){
            elements[i].disabled = bytecode;
            if(bytecode && elements[i].checked){
                elements[i].checked=false;
            }
        }
    }
}

function updateContractType(){
    const extension = getExtension();
    const div = document.getElementById('contract_name_div');
    if(extension === '.sol'){
        div.style.display = 'block';
    }else {
        div.style.display = 'none'
    }
}

function getExtension(){
    const filename = document.getElementById('file').value;
    return filename.substr(filename.lastIndexOf('.'))
}

function clearSession() {
    document.cookie="session=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
}
//
// function guessContractName() {
//     var filename = document.getElementById('file').value
//     document.getElementById('contract_filenames').value = filename.substring(0,filename.length-4)
// }